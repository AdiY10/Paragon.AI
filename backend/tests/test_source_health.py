from datetime import timedelta
import pytest
from django.utils import timezone
from apps.sources.catalog import sync_catalog
from apps.sources.health import record_check,health_status,health_payload
from apps.sources.models import SourceHealth,SourceCheck
from backend.tests.test_accounts import member

pytestmark=pytest.mark.django_db


def checked(*,key='run-1',succeeded=True,scope='county:36111',days=0,source='SRC-06',**kwargs):
    return record_check(source_id=source,scope=scope,run_key=key,succeeded=succeeded,
        completed_at=timezone.now()-timedelta(days=days),error_code='' if succeeded else 'TIMEOUT',**kwargs)


def test_failures_are_scoped_and_raise_alert_after_second_failure():
    sync_catalog()
    a,_=checked()
    checked(key='other',scope='county:09190')
    a,_=checked(key='fail-1',succeeded=False)
    assert health_status(a)=='Failing'
    assert not health_payload(a)['needs_alert']
    last_good=a.last_success_at
    a,_=checked(key='fail-2',succeeded=False)
    assert a.last_success_at==last_good
    assert health_payload(a)['needs_alert']
    b=SourceHealth.objects.select_related('source').get(scope='county:09190')
    assert health_status(b)=='OK'
    a,_=checked(key='recovery')
    assert health_status(a)=='OK' and a.consecutive_failures==0


def test_stale_means_time_since_successful_check_not_data_period():
    sync_catalog()
    state,_=checked(days=22)
    assert health_status(state)=='Stale'
    state,_=checked(key='confirmed-unchanged')
    assert health_status(state)=='OK'


def test_replayed_check_does_not_refresh_time_or_increment_failures():
    sync_catalog()
    state,_=checked(days=2)
    original=state.last_checked_at
    state,created=checked(days=1)
    assert not created and state.last_checked_at==original
    checked(key='failure',succeeded=False)
    state,created=checked(key='failure',succeeded=False)
    assert not created and state.consecutive_failures==1
    assert SourceCheck.objects.count()==2


def test_old_capture_does_not_clear_new_failure():
    sync_catalog()
    state,_=checked(key='failure',succeeded=False)
    state,_=checked(key='old-capture',days=2)
    assert health_status(state)=='Failing'
    assert state.last_success_at is not None
    assert state.last_success_at<state.last_checked_at


def test_unprocessed_overture_release_stales_even_when_listing_check_succeeds():
    sync_catalog()
    state,_=checked(source='SRC-13',available_release='2026-10-21.0',
        available_since=timezone.now()-timedelta(days=15))
    assert health_status(state)=='Stale'
    state,_=checked(source='SRC-13',key='same-release',available_release='2026-10-21.0')
    assert health_status(state)=='Stale'


def test_private_source_api_does_not_hide_one_scope_failure(client):
    sync_catalog()
    checked(scope='county:36111')
    checked(scope='county:09190',key='failed',succeeded=False)
    user,_=member();client.force_login(user)
    data=client.get('/api/sources/').json()
    qcew=next(s for s in data if s['id']=='SRC-06')
    assert qcew['status']=='Failing'
    assert len(qcew['health_scopes'])==2


def test_raw_exception_text_cannot_be_used_as_error_code():
    sync_catalog()
    with pytest.raises(ValueError,match='sanitized'):
        record_check(source_id='SRC-06',scope='county:36111',run_key='bad',succeeded=False,error_code='secret token=xyz')
    assert not SourceCheck.objects.exists()


def test_late_success_reconciles_only_failures_after_its_actual_time():
    sync_catalog()
    checked(key='early-failure',days=5,succeeded=False)
    checked(key='late-failure',days=1,succeeded=False)
    state,_=checked(key='historical-success',days=3)
    assert state.consecutive_failures==1
    assert health_status(state)=='Failing'


def test_health_failure_keeps_last_good_snapshot(tmp_path):
    from backend.tests.test_snapshots import publish
    sync_catalog()
    snapshot,_=publish(tmp_path)
    state,_=record_check(source_id='SRC-13',scope=snapshot.scope,run_key='good',succeeded=True,snapshot=snapshot)
    state,_=record_check(source_id='SRC-13',scope=snapshot.scope,run_key='bad',succeeded=False,error_code='SCHEMA_ERROR')
    assert state.latest_snapshot_id==snapshot.pk
    payload=health_payload(state)
    assert payload['status']=='Failing' and payload['data_period']==snapshot.data_period


def test_simultaneous_success_and_failure_remain_visibly_failing():
    sync_catalog()
    when=timezone.now()-timedelta(seconds=1)
    record_check(source_id='SRC-06',scope='county:36111',run_key='same-time-success',succeeded=True,completed_at=when)
    state,_=record_check(source_id='SRC-06',scope='county:36111',run_key='same-time-failure',succeeded=False,completed_at=when,error_code='TIMEOUT')
    assert health_status(state)=='Failing'
    assert state.error_code=='TIMEOUT'
