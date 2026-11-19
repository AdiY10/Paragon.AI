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
    password=forms.CharField(max_length=1024,strip=False,label='Password',widget=forms.PasswordInput(attrs={'autocomplete':'current-password'}))


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
        retry_after=reserve_attempt(email,request.META.get('REMOTE_ADDR',''))
        if retry_after:
            status=429;error='Too many sign-in attempts. Please try again later.'
        elif form.is_valid():
            membership=Membership.objects.select_related('user').filter(email=email,active=True).first()
            password=form.cleaned_data['password']
            # Authenticate against a non-existent username for unavailable users,
            # retaining Django's dummy password hashing instead of a quick failure.
            username=membership.user.get_username() if membership and membership.user else '__unavailable_password_account__'
            user=authenticate(request,username=username,password=password,backend='django.contrib.auth.backends.ModelBackend')
            if user and membership and membership.user_id==user.pk and user.is_active:
                login(request,user,backend='django.contrib.auth.backends.ModelBackend')
                AccessAuditEvent.objects.create(actor=user,membership=membership,action='password_login',after={'method':'password'})
                return redirect(next_path)
            status=401;error='The email or password is incorrect, or access is unavailable.'
        else:
            status=401;error='The email or password is incorrect, or access is unavailable.'
    response=render(request,'account/password_login.html',{'form':form,'error':error,'next':next_path,
        'oidc_available':bool(settings.SOCIALACCOUNT_PROVIDERS)},status=status)
    if retry_after:response['Retry-After']=str(retry_after)
    return response


@never_cache
@require_POST
def sign_out(request):
    logout(request)
    return redirect(settings.LOGIN_URL)
