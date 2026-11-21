"""Opt-in password access using Django sessions, active membership, and DB throttles."""
from datetime import timedelta
import math
from django.conf import settings
from django.contrib.auth import authenticate,login,logout
from django.contrib.auth.decorators import login_not_required
from django import forms
from django.db import transaction
from django.http import HttpResponseNotFound
from django.shortcuts import render,redirect
from django.utils import timezone
from django.utils.crypto import salted_hmac
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters,sensitive_variables
from django.views.decorators.http import require_http_methods,require_POST
from .models import LoginThrottle,Membership,AccessAuditEvent

WINDOW=timedelta(minutes=15)


class AccessForm(forms.Form):
    email=forms.EmailField(max_length=254,label='Email',widget=forms.EmailInput(attrs={'autocomplete':'username'}))
    password=forms.CharField(max_length=1024,strip=False,label='Password',required=False,widget=forms.PasswordInput(attrs={'autocomplete':'current-password'}))


@transaction.atomic
def reserve_attempt(email,ip):
    now=timezone.now()
    buckets=sorted([(salted_hmac('password-login','account:'+email.lower(),algorithm='sha256').hexdigest(),8),
        (salted_hmac('password-login','ip:'+ip,algorithm='sha256').hexdigest(),30)])
    rows=[]
    for key,limit in buckets:
        LoginThrottle.objects.get_or_create(key=key,defaults={'window_start':now})
        bucket=LoginThrottle.objects.select_for_update().get(pk=key)
        if now-bucket.window_start>=WINDOW:
            bucket.window_start=now;bucket.attempts=0;bucket.save()
        if bucket.attempts>=limit:
            return max(1,math.ceil((bucket.window_start+WINDOW-now).total_seconds()))
        rows.append(bucket)
    for bucket in rows:
        bucket.attempts+=1;bucket.save(update_fields=['attempts'])
    return 0


def release_account_attempt(email):
    """A successful sign-in clears the account bucket, so typos before it don't add up; the IP bucket stays."""
    key=salted_hmac('password-login','account:'+email.lower(),algorithm='sha256').hexdigest()
    LoginThrottle.objects.filter(pk=key).update(attempts=0)


def client_ip(request):
    """The client address as seen by the outermost trusted proxy (TRUSTED_PROXY_COUNT), else REMOTE_ADDR.

    X-Forwarded-For entries left of the trusted hops are client-controlled and ignored.
    """
    hops=getattr(settings,'TRUSTED_PROXY_COUNT',0)
    if hops>0:
        chain=[p.strip() for p in request.META.get('HTTP_X_FORWARDED_FOR','').split(',') if p.strip()]
        if len(chain)>=hops:return chain[-hops]
    return request.META.get('REMOTE_ADDR','')


LOCAL_HOSTS={'127.0.0.1','localhost'}


def local_shared_password_enabled(request):
    """Local-preview convenience only: a shared password for any email.

    Active only when LOCAL_SHARED_PASSWORD is set (never in committed settings) AND the
    request is addressed to this machine, so a deployed site can never accept it.
    """
    secret=getattr(settings,'LOCAL_SHARED_PASSWORD','') or ''
    if not (secret and getattr(settings,'LOCAL_PREVIEW',False)):return False
    # A same-machine reverse proxy also connects from 127.0.0.1, so any forwarding header disqualifies.
    if any(k in request.META for k in ('HTTP_X_FORWARDED_FOR','HTTP_X_REAL_IP','HTTP_FORWARDED')):return False
    host=request.get_host().rsplit(':',1)[0].strip('[]')
    return host in LOCAL_HOSTS and request.META.get('REMOTE_ADDR') in ('127.0.0.1','::1')


@sensitive_variables('password')
def local_shared_login(request,email,password):
    from django.contrib.auth import get_user_model
    from django.utils.crypto import constant_time_compare
    if not constant_time_compare(password,settings.LOCAL_SHARED_PASSWORD):return None
    User=get_user_model()
    user,_=User.objects.get_or_create(username=email,defaults={'email':email})
    membership=Membership.objects.filter(email=email).first()
    if membership is None:
        membership=Membership.objects.create(email=email,user=user,role=Membership.Role.MEMBER)
    elif membership.user_id is None:
        membership.user=user;membership.save(update_fields=['user'])
    if not membership.active or membership.user_id!=user.pk or not user.is_active:return None
    return user,membership


def email_only_login(email):
    """Guest-list entry for an active *member*; administrators always use their password."""
    from django.contrib.auth import get_user_model
    membership=Membership.objects.select_related('user').filter(email=email,active=True).first()
    if membership is None or membership.role!=Membership.Role.MEMBER:return None
    user=membership.user
    if user is None:
        User=get_user_model()
        user,created=User.objects.get_or_create(username=email,defaults={'email':email})
        if created:
            user.set_unusable_password();user.save(update_fields=['password'])
        membership.user=user;membership.save(update_fields=['user'])
    if not user.is_active:return None
    return user,membership


def return_path(value):
    return value if isinstance(value,str) and value.startswith('/') and not value.startswith('//') and '\\' not in value and not any(ord(c)<32 for c in value) else '/'


@login_not_required
@never_cache
@require_http_methods(['GET','POST'])
@sensitive_post_parameters('password','email')
@sensitive_variables('password')
def sign_in(request):
    if not settings.PASSWORD_ACCESS_ENABLED:return HttpResponseNotFound()
    next_path=return_path(request.POST.get('next',request.GET.get('next','/')))
    if request.user.is_authenticated:return redirect(next_path)
    form=AccessForm(request.POST if request.method=='POST' else None)
    status=200;retry_after=0;error=''
    if request.method=='POST':
        email=request.POST.get('email','')[:254].strip().lower()
        retry_after=reserve_attempt(email,client_ip(request))
        if retry_after:
            status=429;error='Too many sign-in attempts. Please try again later.'
        elif form.is_valid() and settings.EMAIL_ONLY_ACCESS and not form.cleaned_data['password'] and \
                (guest:=email_only_login(email)):
            user,membership=guest
            _signed_in(request,user,membership,'email_only',email)
            return redirect(next_path)
        elif form.is_valid() and settings.EMAIL_ONLY_ACCESS and not form.cleaned_data['password']:
            known=Membership.objects.filter(email=email,active=True).first()
            if known and known.role==Membership.Role.ADMIN:
                status=401;error='Administrators sign in with their password.'
            else:
                status=401;error='This email does not have access. Ask your administrator to add it.'
        elif form.is_valid() and local_shared_password_enabled(request) and \
                (shared:=local_shared_login(request,email,form.cleaned_data['password'])):
            user,membership=shared
            _signed_in(request,user,membership,'local_shared_password',email)
            return redirect(next_path)
        elif form.is_valid():
            membership=Membership.objects.select_related('user').filter(email=email,active=True).first()
            password=form.cleaned_data['password']
            # Authenticate against a non-existent username for unavailable users,
            # retaining Django's dummy password hashing instead of a quick failure.
            username=membership.user.get_username() if membership and membership.user else '__unavailable_password_account__'
            user=authenticate(request,username=username,password=password,backend='django.contrib.auth.backends.ModelBackend')
            if user and membership and membership.user_id==user.pk and user.is_active:
                _signed_in(request,user,membership,'password',email)
                return redirect(next_path)
            if membership:
                AccessAuditEvent.objects.create(actor=None,membership=membership,action='password_login_failed')
            status=401;error='The email or password is incorrect, or access is unavailable.'
        else:
            status=401;error='The email or password is incorrect, or access is unavailable.'
    response=render(request,'account/password_login.html',{'form':form,'error':error,'next':next_path,
        'oidc_available':bool(settings.SOCIALACCOUNT_PROVIDERS),'local_shared':local_shared_password_enabled(request),
        'email_only':settings.EMAIL_ONLY_ACCESS},status=status)
    if retry_after:response['Retry-After']=str(retry_after)
    return response


def _signed_in(request,user,membership,method,email):
    login(request,user,backend='django.contrib.auth.backends.ModelBackend')
    request.session['signed_in_at']=int(timezone.now().timestamp())
    release_account_attempt(email)
    AccessAuditEvent.objects.create(actor=user,membership=membership,action='password_login',after={'method':method})


@never_cache
@require_POST
def sign_out(request):
    membership=getattr(request,'membership',None)
    if membership:
        AccessAuditEvent.objects.create(actor=request.user,membership=membership,action='logout')
    logout(request)
    return redirect(settings.LOGIN_URL)
