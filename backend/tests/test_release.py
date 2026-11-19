from io import StringIO
import json
from pathlib import Path
import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from apps.accounts.models import Membership
from apps.locations.models import Location,WorkspaceImport

pytestmark=pytest.mark.django_db
PASSWORD='Isolated-host-bootstrap-password-839!'
EMAIL='host-test@example.invalid'

@pytest.fixture
def bootstrap(settings,monkeypatch):
    settings.PASSWORD_ACCESS_ENABLED=True
    monkeypatch.setenv('ACCESS_BOOTSTRAP_EMAIL',EMAIL)
    monkeypatch.setenv('ACCESS_BOOTSTRAP_PASSWORD',PASSWORD)


def test_secret_bootstrap_creates_account_once_and_does_not_reset_rotated_password(bootstrap,monkeypatch):
    out=StringIO();call_command('bootstrap_access',stdout=out)
    member=Membership.objects.get();assert member.role=='admin' and member.user.check_password(PASSWORD)
    member.user.set_password(PASSWORD+'changed');member.user.save()
    monkeypatch.setenv('ACCESS_BOOTSTRAP_PASSWORD',PASSWORD)
    call_command('bootstrap_access',stdout=out)
    member.user.refresh_from_db();assert member.user.check_password(PASSWORD+'changed')
    assert PASSWORD not in out.getvalue() and EMAIL not in out.getvalue()


def test_stale_bootstrap_never_reactivates_revoked_accounts(bootstrap,monkeypatch):
    call_command('bootstrap_access',stdout=StringIO());member=Membership.objects.get();member.active=False;member.save()
    monkeypatch.setenv('ACCESS_BOOTSTRAP_PASSWORD',PASSWORD)
    call_command('bootstrap_access',stdout=StringIO())
    member.refresh_from_db();assert not member.active


def test_bootstrap_cannot_claim_existing_oidc_identity(bootstrap):
    get_user_model().objects.create_user(username='oidc-test',email=EMAIL)
    with pytest.raises(CommandError,match='Existing identity'):call_command('bootstrap_access')
    assert not Membership.objects.exists()


def test_disabled_password_mode_does_not_create_accounts(bootstrap,settings):
    settings.PASSWORD_ACCESS_ENABLED=False;call_command('bootstrap_access')
    assert not Membership.objects.exists()


def test_existing_admin_allows_bootstrap_secret_removal(bootstrap,monkeypatch):
    call_command('bootstrap_access',stdout=StringIO())
    monkeypatch.delenv('ACCESS_BOOTSTRAP_EMAIL');monkeypatch.delenv('ACCESS_BOOTSTRAP_PASSWORD',raising=False)
    call_command('bootstrap_access')
    assert Membership.objects.count()==1


def test_unconfigured_password_host_fails_closed(settings,monkeypatch):
    settings.PASSWORD_ACCESS_ENABLED=True
    monkeypatch.delenv('ACCESS_BOOTSTRAP_EMAIL',raising=False);monkeypatch.delenv('ACCESS_BOOTSTRAP_PASSWORD',raising=False)
    with pytest.raises(CommandError,match='Configure both'):call_command('bootstrap_access')


def test_weak_bootstrap_secret_is_sanitized(bootstrap,monkeypatch):
    secret='weak-secret';monkeypatch.setenv('ACCESS_BOOTSTRAP_PASSWORD',secret)
    with pytest.raises(CommandError) as error:call_command('bootstrap_access')
    assert secret not in str(error.value) and not Membership.objects.exists()


def test_release_runs_migration_before_seed_and_replays_without_duplicates(settings,tmp_path,monkeypatch):
    settings.SOURCE_ARTIFACT_ROOT=tmp_path/'private-artifacts'
    monkeypatch.delenv('WORKSPACE_IMPORT_PATH',raising=False);monkeypatch.delenv('WORKSPACE_IMPORT_SHA256',raising=False)
    out=StringIO();call_command('prepare_release',stdout=out);call_command('prepare_release',stdout=out)
    assert Location.objects.count()==36


def test_release_verifies_private_export_before_seeding(settings,tmp_path,monkeypatch):
    import hashlib
    settings.SOURCE_ARTIFACT_ROOT=tmp_path/'private-artifacts'
    data=json.loads(Path('sites/temporary/data/bootstrap.json').read_text());data['schema_version']=3
    raw=json.dumps(data).encode();path=tmp_path/'private-export.json';path.write_bytes(raw)
    monkeypatch.setenv('WORKSPACE_IMPORT_PATH',str(path));monkeypatch.setenv('WORKSPACE_IMPORT_SHA256','0'*64)
    with pytest.raises(CommandError,match='checksum mismatch'):call_command('prepare_release',stdout=StringIO())
    assert not Location.objects.exists()
    monkeypatch.setenv('WORKSPACE_IMPORT_SHA256',hashlib.sha256(raw).hexdigest())
    call_command('prepare_release',stdout=StringIO());call_command('prepare_release',stdout=StringIO())
    assert Location.objects.count()==36 and WorkspaceImport.objects.count()==1
