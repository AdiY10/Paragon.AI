from types import SimpleNamespace
import pytest
from allauth.account.models import EmailAddress
from allauth.socialaccount.models import SocialAccount, SocialLogin
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.core.management import call_command
from django.core.management.base import CommandError
from apps.accounts.models import Membership
from apps.accounts.adapters import InviteOnlySocialAdapter, ClosedAccountAdapter

pytestmark = pytest.mark.django_db


def member(email='member@example.org', role='member'):
    user = get_user_model().objects.create_user(username=email, email=email)
    membership = Membership.objects.create(email=email, user=user, role=role)
    return user, membership


def login_payload(email, verified):
    return SocialLogin(user=get_user_model()(email=email),
        account=SocialAccount(provider='openid_connect', uid='subject-1'),
        email_addresses=[EmailAddress(email=email, verified=verified, primary=True)])


def test_invited_member_can_access_session(client):
    user, _ = member()
    client.force_login(user)
    payload = client.get('/api/session/').json()
    assert payload['email'] == user.email and payload['role'] == 'member'
    assert len(payload['csrfToken']) == 64


def test_revocation_denies_next_request_and_logs_out(client):
    user, membership = member()
    client.force_login(user)
    assert client.get('/api/session/').status_code == 200
    membership.active = False
    membership.save()
    assert client.get('/api/session/').status_code == 403
    assert '_auth_user_id' not in client.session


def test_authenticated_user_without_invitation_is_denied(client):
    user = get_user_model().objects.create_user(username='outsider')
    client.force_login(user)
    assert client.get('/api/session/').status_code == 403


def test_admin_invites_normalized_member(client):
    admin, _ = member('admin@example.org', 'admin')
    client.force_login(admin)
    response = client.post('/api/admin/users/', {'email': 'New@Example.org'}, content_type='application/json')
    assert response.status_code == 201
    invitation = Membership.objects.get(email='new@example.org')
    assert invitation.role == 'member'
    assert invitation.user_id is None
    assert invitation.invited_by == admin


def test_member_cannot_invite_or_list_users(client):
    user, _ = member()
    client.force_login(user)
    assert client.get('/api/admin/users/').status_code == 403
    assert client.post('/api/admin/users/', {'email':'new@example.org'}).status_code == 403


def test_admin_removes_user(client):
    admin, _ = member('admin@example.org', 'admin')
    _, target = member()
    client.force_login(admin)
    assert client.delete(f'/api/admin/users/{target.id}/').status_code == 204
    target.refresh_from_db()
    assert not target.active


def test_last_admin_cannot_be_removed(client):
    admin, target = member('admin@example.org', 'admin')
    client.force_login(admin)
    assert client.delete(f'/api/admin/users/{target.id}/').status_code == 409


def test_reinvite_does_not_restore_removed_access(client):
    admin, _ = member('admin@example.org', 'admin')
    _, target = member()
    target.active = False
    target.save()
    client.force_login(admin)
    response = client.post('/api/admin/users/', {'email':target.email}, content_type='application/json')
    assert response.status_code == 409
    target.refresh_from_db()
    assert not target.active


def test_verified_invited_oidc_identity_is_accepted(rf):
    Membership.objects.create(email='member@example.org')
    payload = login_payload('Member@Example.org', True)
    adapter = InviteOnlySocialAdapter()
    adapter.pre_social_login(rf.get('/'), payload)
    assert payload.user.email == 'member@example.org'
    assert adapter.is_open_for_signup(rf.get('/'), payload)


@pytest.mark.parametrize('invited,verified,active', [(False,True,True),(True,False,True),(True,True,False)])
def test_oidc_requires_active_invitation_and_verified_email(rf, invited, verified, active):
    if invited:
        Membership.objects.create(email='member@example.org', active=active)
    with pytest.raises(PermissionDenied):
        InviteOnlySocialAdapter().pre_social_login(rf.get('/'), login_payload('member@example.org', verified))


def test_password_signup_is_closed(rf):
    assert not ClosedAccountAdapter().is_open_for_signup(rf.get('/'))


def test_sign_in_is_public_without_business_data(client):
    response = client.get('/accounts/login/')
    assert response.status_code == 200
    assert b'Access is by invitation only' in response.content
    assert b'Organization sign-in is not configured' in response.content


def test_bootstrap_invitation_has_no_password_or_user():
    call_command('invite_admin', 'Admin@Example.org')
    invitation = Membership.objects.get(email='admin@example.org')
    assert invitation.role == 'admin'
    assert invitation.user_id is None
    with pytest.raises(CommandError):
        call_command('invite_admin', 'admin@example.org')


def test_oidc_signup_binds_membership_without_password(rf):
    invitation = Membership.objects.create(email='member@example.org')
    request = rf.get('/')
    request.session = {}
    payload = login_payload('member@example.org', True)
    adapter = InviteOnlySocialAdapter()
    user = adapter.save_user(request, payload)
    invitation.refresh_from_db()
    assert invitation.user_id == user.pk
    assert not user.has_usable_password()
    assert EmailAddress.objects.get(user=user).verified


def test_existing_identity_cannot_use_a_different_membership(rf):
    user, _ = member('old@example.org')
    Membership.objects.create(email='new@example.org')
    payload = login_payload('new@example.org', True)
    payload.user = user
    payload.account.user = user
    payload.account.save()
    with pytest.raises(PermissionDenied):
        InviteOnlySocialAdapter().pre_social_login(rf.get('/'), payload)


def test_invitation_mutations_require_csrf():
    from django.test import Client
    admin, _ = member('admin@example.org', 'admin')
    client = Client(enforce_csrf_checks=True)
    client.force_login(admin)
    response = client.post('/api/admin/users/', {'email':'new@example.org'}, content_type='application/json')
    assert response.status_code == 403


def test_role_promotion_takes_effect_on_next_request(client):
    admin, _ = member('admin@example.org', 'admin')
    target, membership = member()
    client.force_login(admin)
    response = client.patch(f'/api/admin/users/{membership.id}/', {'role':'admin'}, content_type='application/json')
    assert response.status_code == 200
    client.force_login(target)
    assert client.get('/api/admin/users/').status_code == 200
    event = membership.audit_events.get(action='role_changed')
    assert event.before['role'] == 'member'
    assert event.after['role'] == 'admin'
    assert event.actor == admin


def test_pending_admin_cannot_allow_last_signed_in_admin_to_be_demoted(client):
    admin, membership = member('admin@example.org', 'admin')
    Membership.objects.create(email='pending@example.org', role='admin')
    client.force_login(admin)
    assert client.patch(f'/api/admin/users/{membership.id}/', {'role':'member'}, content_type='application/json').status_code == 409
    assert client.delete(f'/api/admin/users/{membership.id}/').status_code == 409


def test_member_cannot_promote_self(client):
    user, membership = member()
    client.force_login(user)
    assert client.patch(f'/api/admin/users/{membership.id}/', {'role':'admin'}, content_type='application/json').status_code == 403


def test_invitation_and_removal_are_audited(client):
    admin, _ = member('admin@example.org', 'admin')
    client.force_login(admin)
    assert client.post('/api/admin/users/', {'email':'new@example.org'}, content_type='application/json').status_code == 201
    invitation = Membership.objects.get(email='new@example.org')
    assert invitation.audit_events.get().action == 'invited'
    assert client.delete(f'/api/admin/users/{invitation.id}/').status_code == 204
    assert list(invitation.audit_events.order_by('created_at').values_list('action',flat=True)) == ['invited','removed']
