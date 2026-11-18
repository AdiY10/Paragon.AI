from dataclasses import asdict
from datetime import datetime,timezone,timedelta
from unittest.mock import patch
import uuid
import pytest
from django_q.models import OrmQ
from apps.operations.calendar import CalendarRule
from apps.operations.models import JobSchedule,ScheduleOccurrence,JobRun,SchedulerState
from apps.operations.scheduler import sync_schedules,dispatch_due,release_leader
from backend.tests.test_accounts import member

pytestmark=pytest.mark.django_db


def anchor():return datetime(2026,11,17,12,tzinfo=timezone.utc)


def schedule():
    return JobSchedule.objects.create(name='catalog',kind='sync_source_catalog',enabled=True,
        calendar=asdict(CalendarRule('daily',6)),next_due_at=anchor()-timedelta(days=3,hours=1))


def test_missing_source_handlers_remain_disabled_and_visible(client):
    assert sync_schedules(enable_available=True,now=anchor())==8
    assert not JobSchedule.objects.filter(enabled=True).exists()
    user,_=member('admin@example.org','admin');client.force_login(user)
    data=client.get('/api/admin/schedules/').json()
    assert len(data['schedules'])==8
    assert all(s['blocked_reason']=='HANDLER_NOT_IMPLEMENTED' for s in data['schedules'])


def test_dispatch_coalesces_backlog_and_advances_persisted_cursor():
    item=schedule();owner=uuid.uuid4()
    result=dispatch_due(owner=owner,now=anchor())
    assert result['leader'] is True and result['dispatched']==1 and result['blocked']==0
    occurrence=ScheduleOccurrence.objects.get()
    assert occurrence.missed_count==3 and occurrence.delay_seconds==3600
    assert occurrence.scheduled_for==anchor()-timedelta(hours=1)
    item.refresh_from_db();assert item.next_due_at==datetime(2026,11,18,11,tzinfo=timezone.utc)
    assert dispatch_due(owner=owner,now=anchor())['dispatched']==0
    assert JobRun.objects.count()==1 and OrmQ.objects.count()==1


def test_another_scheduler_cannot_dispatch_under_live_leader_lease():
    schedule();owner=uuid.uuid4()
    dispatch_due(owner=owner,now=anchor())
    assert dispatch_due(owner=uuid.uuid4(),now=anchor())['leader'] is False
    release_leader(owner)
    assert dispatch_due(owner=uuid.uuid4(),now=anchor()+timedelta(seconds=61))['leader'] is True


def test_failed_enqueue_keeps_cursor_and_occurrence_history_unchanged():
    item=schedule();original=item.next_due_at
    with patch('apps.operations.scheduler.enqueue_job',side_effect=OSError('queue failure')):
        with pytest.raises(OSError):dispatch_due(owner=uuid.uuid4(),now=anchor())
    item.refresh_from_db()
    assert item.next_due_at==original
    assert not ScheduleOccurrence.objects.exists() and not JobRun.objects.exists()


def test_enabled_missing_handler_is_blocked_without_fake_success():
    item=schedule();item.kind='sec_daily';item.save()
    assert dispatch_due(owner=uuid.uuid4(),now=anchor())['blocked']==1
    assert not JobRun.objects.exists()


def test_schedule_metadata_is_private(client):
    assert client.get('/api/admin/schedules/').status_code==403
    user,_=member();client.force_login(user)
    assert client.get('/api/admin/schedules/').status_code==403


def test_expired_scheduler_lease_can_be_reclaimed():
    schedule()
    SchedulerState.objects.create(name='primary',owner=uuid.uuid4(),lease_until=anchor()-timedelta(seconds=1))
    assert dispatch_due(owner=uuid.uuid4(),now=anchor())['dispatched']==1


def test_rewound_cursor_does_not_duplicate_an_already_dispatched_local_date():
    item=schedule();owner=uuid.uuid4()
    dispatch_due(owner=owner,now=anchor())
    item.next_due_at=anchor()-timedelta(hours=1);item.save()
    assert dispatch_due(owner=owner,now=anchor())['dispatched']==0
    assert ScheduleOccurrence.objects.count()==1 and JobRun.objects.count()==1


@pytest.mark.django_db(transaction=True)
def test_concurrent_scheduler_candidates_enqueue_once():
    from concurrent.futures import ThreadPoolExecutor
    from django.db import connection,connections
    if connection.vendor!='postgresql':pytest.skip('Leader locking requires PostgreSQL')
    schedule()
    def dispatch(_):
        try:return dispatch_due(owner=uuid.uuid4(),now=anchor())
        finally:connections.close_all()
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(dispatch,range(2)))
    assert sum(r['dispatched'] for r in results)==1
    assert ScheduleOccurrence.objects.count()==1 and OrmQ.objects.count()==1
