from datetime import timedelta
from io import StringIO
from unittest.mock import patch
import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import Client
from django.utils import timezone
from apps.accounts.models import Membership,LoginThrottle,AccessAuditEvent
from apps.accounts.password_access import reserve_attempt
from backend.tests.test_accounts import member

pytestmark=pytest.mark.django_db
PASSWORD='Only-for-isolated-tests-Password!937'

@pytest.fixture
def password_mode(settings):
    settings.PASSWORD_ACCESS_ENABLED=True;settings.LOGIN_URL='/access/login/'


def setup_account():
    user,membership=member();user.set_password(PASSWORD);user.save();return user,membership


def test_password_access_is_explicitly_disabled_by_default(client):
    assert client.get('/access/login/').status_code==404


def test_anonymous_pages_and_data_are_gated_in_password_mode(client,password_mode):
    assert client.get('/').status_code==302 and client.get('/').url.startswith('/access/login/')
    assert client.get('/api/locations/').status_code==403
    response=client.get('/access/login/')
    assert response.status_code==200 and b'Password' in response.content and b'no-store' in response['Cache-Control'].encode()
    assert client.get('/health/').json()=={'status':'ok'}


def test_named_password_signin_signout_and_no_secret_echo(client,password_mode):
    user,_=setup_account()
    response=client.post('/access/login/',{'email':user.email,'password':PASSWORD})
    assert response.status_code==302 and response.url=='/'
    assert client.get('/api/session/').json()['email']==user.email
    assert client.get('/api/session/').json()['logout_url']=='/access/logout/'
    assert client.get('/access/logout/').status_code==405
    assert client.post('/access/logout/').status_code==302
    assert client.get('/api/session/').status_code==403
    assert PASSWORD not in str(list(AccessAuditEvent.objects.values('after')))


def test_wrong_unknown_and_revoked_users_have_same_message(password_mode):
    user,membership=setup_account();client=Client()
    bodies=[]
    for email in [user.email,'unknown@example.invalid']:
        response=client.post('/access/login/',{'email':email,'password':'wrong-password'})
        assert response.status_code==401 and b'wrong-password' not in response.content
        bodies.append(response.context['error'])
    membership.active=False;membership.save()
    response=client.post('/access/login/',{'email':user.email,'password':PASSWORD})
    assert response.status_code==401 and response.context['error']==bodies[0]==bodies[1]
    assert client.get('/api/locations/').status_code==403


def test_login_and_logout_require_csrf(password_mode):
    user,_=setup_account();client=Client(enforce_csrf_checks=True)
    assert client.post('/access/login/',{'email':user.email,'password':PASSWORD}).status_code==403
    page=client.get('/access/login/');token=page.context['csrf_token']
    assert client.post('/access/login/',{'email':user.email,'password':PASSWORD,'csrfmiddlewaretoken':token}).status_code==302
    assert client.post('/access/logout/').status_code==403


def test_attempt_limit_is_shared_and_expires(password_mode):
    user,_=setup_account()
    for _ in range(8):assert Client().post('/access/login/',{'email':user.email,'password':'wrong'}).status_code==401
    response=Client().post('/access/login/',{'email':user.email,'password':PASSWORD})
    assert response.status_code==429 and int(response['Retry-After'])>0
    assert all(user.email not in row.key and '127.0.0.1' not in row.key for row in LoginThrottle.objects.all())
    LoginThrottle.objects.update(window_start=timezone.now()-timedelta(minutes=16))
    assert Client().post('/access/login/',{'email':user.email,'password':PASSWORD}).status_code==302


def test_rotation_invalidates_existing_sessions_without_reactivation(password_mode):
    user,membership=setup_account();client=Client();client.post('/access/login/',{'email':user.email,'password':PASSWORD})
    new_password='Different-isolated-test-secret!842'
    with patch('sys.stdin',StringIO(new_password+'\n')):
        call_command('set_access_password',user.email,password_stdin=True,stdout=StringIO())
    user.refresh_from_db();assert user.check_password(new_password) and user.password!=new_password
    assert client.get('/api/session/').status_code==403
    membership.active=False;membership.save()
    with patch('sys.stdin',StringIO(new_password+'\n')),pytest.raises(CommandError,match='revoked'):
        call_command('set_access_password',user.email,password_stdin=True,stdout=StringIO())


def test_provision_command_uses_hashes_and_explicit_roles(password_mode):
    output=StringIO()
    with patch('sys.stdin',StringIO(PASSWORD+'\n')):
        call_command('set_access_password','new@example.invalid',role='admin',password_stdin=True,stdout=output)
    membership=Membership.objects.get(email='new@example.invalid')
    assert membership.role=='admin' and membership.user.check_password(PASSWORD)
    assert PASSWORD not in output.getvalue() and membership.user.password!=PASSWORD
    with patch('sys.stdin',StringIO('short\n')),pytest.raises(CommandError):
        call_command('set_access_password','second@example.invalid',password_stdin=True,stdout=output)
    assert not Membership.objects.filter(email='second@example.invalid').exists()


@pytest.mark.parametrize('next_path',['https://evil.example','//evil.example','/\\evil.example','/\nhttps://evil.example'])
def test_login_redirect_cannot_leave_origin(client,password_mode,next_path):
    user,_=setup_account();response=client.post('/access/login/',{'email':user.email,'password':PASSWORD,'next':next_path})
    assert response.status_code==302 and response.url=='/'


@pytest.mark.django_db(transaction=True)
def test_concurrent_attempts_do_not_bypass_limit():
    from concurrent.futures import ThreadPoolExecutor
    from django.db import connection,connections
    if connection.vendor!='postgresql':pytest.skip('Login throttling locks require PostgreSQL')
    def attempt(_):
        try:return reserve_attempt('test-only@example.invalid','127.0.0.1')
        finally:connections.close_all()
    with ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(attempt,range(12)))
    assert results.count(0)==8


# ---- local preview shared password (never active on a deployed host) -----------------

import pytest as _pt
import secrets as _secrets
SHARED = _secrets.token_urlsafe(12)


@_pt.mark.django_db
def test_local_shared_password_signs_in_any_email_on_localhost_only(client, settings):
    settings.PASSWORD_ACCESS_ENABLED = True
    settings.ALLOWED_HOSTS = ['127.0.0.1', 'localhost', 'radar.example']
    settings.LOCAL_PREVIEW = True
    settings.LOCAL_SHARED_PASSWORD = SHARED
    ok = client.post('/access/login/', {'email': 'anyone@example.org', 'password': SHARED},
        HTTP_HOST='127.0.0.1:8765', REMOTE_ADDR='127.0.0.1')
    assert ok.status_code == 302
    client.logout()
    wrong = client.post('/access/login/', {'email': 'anyone@example.org', 'password': 'nope'},
        HTTP_HOST='127.0.0.1:8765', REMOTE_ADDR='127.0.0.1')
    assert wrong.status_code == 401
    remote = client.post('/access/login/', {'email': 'other@example.org', 'password': SHARED},
        HTTP_HOST='radar.example', REMOTE_ADDR='203.0.113.9')
    assert remote.status_code == 401


@_pt.mark.django_db
def test_shared_password_off_without_setting(client, settings):
    settings.PASSWORD_ACCESS_ENABLED = True
    settings.ALLOWED_HOSTS = ['127.0.0.1']
    settings.LOCAL_SHARED_PASSWORD = ''
    r = client.post('/access/login/', {'email': 'x@example.org', 'password': SHARED},
        HTTP_HOST='127.0.0.1', REMOTE_ADDR='127.0.0.1')
    assert r.status_code == 401


def _shared(settings):
    settings.PASSWORD_ACCESS_ENABLED = True
    settings.ALLOWED_HOSTS = ['127.0.0.1', 'localhost']
    settings.LOCAL_SHARED_PASSWORD = SHARED


@_pt.mark.django_db
def test_shared_password_needs_local_preview_and_no_proxy_headers(client, settings):
    _shared(settings)
    settings.LOCAL_PREVIEW = False
    post = lambda **extra: client.post('/access/login/', {'email': 'p@example.org', 'password': SHARED},
        HTTP_HOST='127.0.0.1', REMOTE_ADDR='127.0.0.1', **extra)
    assert post().status_code == 401
    settings.LOCAL_PREVIEW = True
    # A reverse proxy on the same box connects from 127.0.0.1 but adds forwarding headers.
    assert post(HTTP_X_FORWARDED_FOR='203.0.113.9').status_code == 401
    assert post().status_code == 302
    assert Membership.objects.get(email='p@example.org').role == 'member'


def test_production_settings_refuse_the_shared_password(monkeypatch):
    import importlib, sys
    from django.core.exceptions import ImproperlyConfigured
    monkeypatch.setenv('DJANGO_SECRET_KEY', 'x' * 60)
    monkeypatch.setenv('DJANGO_ALLOWED_HOSTS', 'radar.example')
    monkeypatch.setenv('DATABASE_URL', 'postgres://u:p@db/paragon')
    monkeypatch.setenv('LOCAL_SHARED_PASSWORD', SHARED)
    [sys.modules.pop(m, None) for m in ('config.settings.production', 'config.settings.base')]
    with _pt.raises(ImproperlyConfigured):
        importlib.import_module('config.settings.production')
    monkeypatch.delenv('LOCAL_SHARED_PASSWORD')
    [sys.modules.pop(m, None) for m in ('config.settings.production', 'config.settings.base')]
    importlib.import_module('config.settings.production')
    [sys.modules.pop(m, None) for m in ('config.settings.production', 'config.settings.base')]


@_pt.mark.django_db
def test_throttle_uses_trusted_proxy_client_ip_and_success_clears_account(client, settings, password_mode):
    from apps.accounts.password_access import client_ip
    from django.test import RequestFactory
    settings.TRUSTED_PROXY_COUNT = 1
    r = RequestFactory().get('/', REMOTE_ADDR='127.0.0.1', HTTP_X_FORWARDED_FOR='6.6.6.6, 198.51.100.7')
    assert client_ip(r) == '198.51.100.7'  # the spoofable left entry is ignored
    settings.TRUSTED_PROXY_COUNT = 0
    assert client_ip(r) == '127.0.0.1'
    user, membership = setup_account()
    for _ in range(3):
        client.post('/access/login/', {'email': membership.email, 'password': 'wrong-password-123456'})
    assert AccessAuditEvent.objects.filter(action='password_login_failed').count() == 3
    assert client.post('/access/login/', {'email': membership.email, 'password': PASSWORD}).status_code == 302
    assert max(LoginThrottle.objects.values_list('attempts', flat=True)) == 4  # IP bucket keeps counting
    assert sorted(LoginThrottle.objects.values_list('attempts', flat=True))[0] == 0  # account bucket cleared
    client.post('/access/logout/')
    assert AccessAuditEvent.objects.filter(action='logout').count() == 1


@_pt.mark.django_db
def test_absolute_session_cap(client, settings):
    import time
    user, _ = setup_account()
    client.force_login(user)
    assert client.get('/api/locations/').status_code == 200
    session = client.session
    session['signed_in_at'] = int(time.time()) - settings.SESSION_ABSOLUTE_SECONDS - 5
    session.save()
    assert client.get('/api/locations/').status_code == 401
    assert settings.SESSION_COOKIE_AGE == 12 * 3600
