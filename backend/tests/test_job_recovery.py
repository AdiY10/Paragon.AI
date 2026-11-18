from datetime import timedelta
from unittest.mock import patch
import uuid
import pytest
from django.utils import timezone
from django_q.models import OrmQ
from apps.operations.models import JobRun,JobRecoveryEvent
from apps.operations.service import enqueue_job
from apps.operations.recovery import recover_jobs
from apps.operations.runner import execute_job

pytestmark=pytest.mark.django_db


def submitted():
    job,_=enqueue_job(kind='sync_source_catalog',scope='global',dedup_key=uuid.uuid4().hex)
    JobRun.objects.filter(pk=job.pk).update(created_at=timezone.now()-timedelta(minutes=5))
    return job


def test_missing_message_is_requeued_once_and_original_job_is_retained():
    job=submitted();original=job.transport_task_id;OrmQ.objects.all().delete()
    assert recover_jobs()['requeued']==1
    job.refresh_from_db()
    assert job.transport_task_id!=original and job.recovery_count==1
    assert recover_jobs()['untouched']==1
    assert OrmQ.objects.count()==1 and JobRun.objects.count()==1
    assert execute_job(job.id)['status']=='succeeded'


def test_active_lease_and_intact_queue_are_untouched():
    job=submitted()
    assert recover_jobs()['untouched']==1
    JobRun.objects.filter(pk=job.pk).update(status='running',lease_expires_at=timezone.now()+timedelta(minutes=5))
    OrmQ.objects.all().delete()
    assert recover_jobs()['untouched']==1
    assert not JobRecoveryEvent.objects.exists()


def test_expired_attempt_is_fenced_and_locked_receipt_released():
    job=submitted();old=uuid.uuid4()
    JobRun.objects.filter(pk=job.pk).update(status='running',attempts=1,attempt_token=old,
        lease_expires_at=timezone.now()-timedelta(seconds=1))
    OrmQ.objects.update(lock=timezone.now()+timedelta(minutes=10))
    assert recover_jobs()['released']==1
    job.refresh_from_db()
    assert job.attempt_token!=old and job.attempts==1
    assert OrmQ.objects.get().lock<timezone.now()


def test_exhausted_attempt_does_not_start_again():
    job=submitted()
    JobRun.objects.filter(pk=job.pk).update(status='running',attempts=3,lease_expires_at=timezone.now()-timedelta(seconds=1))
    assert recover_jobs()['failed']==1
    job.refresh_from_db();assert job.status=='failed' and job.error_code=='ATTEMPTS_EXHAUSTED'
    assert not OrmQ.objects.exists()


def test_retry_backoff_is_respected_and_ready_receipt_is_not_duplicated():
    job=submitted()
    JobRun.objects.filter(pk=job.pk).update(status='retrying',next_attempt_at=timezone.now()+timedelta(minutes=1))
    assert recover_jobs()['untouched']==1
    JobRun.objects.filter(pk=job.pk).update(next_attempt_at=timezone.now()-timedelta(seconds=1))
    assert recover_jobs()['untouched']==1
    assert OrmQ.objects.count()==1


def test_recovery_enqueue_failure_rolls_back_fence_and_history():
    job=submitted();OrmQ.objects.all().delete()
    with patch('apps.operations.recovery.async_task',side_effect=OSError('queue unavailable')):
        with pytest.raises(OSError):recover_jobs()
    job.refresh_from_db()
    assert job.recovery_count==0 and job.status=='queued'
    assert not JobRecoveryEvent.objects.exists()


def test_repeated_transport_loss_is_bounded():
    job=submitted();OrmQ.objects.all().delete()
    base=timezone.now()
    for attempt in range(6):
        assert recover_jobs(now=base+timedelta(seconds=31*attempt))['requeued']==1
        OrmQ.objects.all().delete()
    assert recover_jobs(now=base+timedelta(seconds=31*6))['failed']==1
    job.refresh_from_db();assert job.status=='failed' and job.error_code=='TRANSPORT_LOST'


def test_intact_older_jobs_do_not_starve_later_recovery_candidates():
    submitted()
    lost=submitted()
    for message in OrmQ.objects.all():
        if message.task.get('id')==lost.transport_task_id:message.delete()
    assert recover_jobs(limit=1)['requeued']==1
    lost.refresh_from_db();assert lost.recovery_count==1


@pytest.mark.django_db(transaction=True)
def test_concurrent_recovery_sweeps_create_one_replacement():
    from concurrent.futures import ThreadPoolExecutor
    from django.db import connection,connections
    if connection.vendor!='postgresql':pytest.skip('Recovery locks require PostgreSQL')
    submitted();OrmQ.objects.all().delete()
    def recover(_):
        try:return recover_jobs()
        finally:connections.close_all()
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(recover,range(2)))
    assert sum(r['requeued'] for r in results)==1
    assert OrmQ.objects.count()==1 and JobRecoveryEvent.objects.count()==1


def test_locked_retry_receipt_is_not_released_without_new_transport_failure():
    from django_q.models import Task
    job=submitted();now=timezone.now()
    JobRun.objects.filter(pk=job.pk).update(status='retrying',next_attempt_at=now-timedelta(seconds=1))
    OrmQ.objects.update(lock=now+timedelta(minutes=35))
    assert recover_jobs(now=now)['untouched']==1
    Task.objects.create(id=job.transport_task_id,name='known_failure',func='apps.operations.runner.execute_job',
        started=now-timedelta(minutes=2),stopped=now-timedelta(minutes=1),success=False,result='SOURCE_ERROR')
    assert recover_jobs(now=now)['released']==1
    # Simulate the same receipt being claimed again; the old failure cannot release it twice.
    OrmQ.objects.update(lock=now+timedelta(minutes=35))
    assert recover_jobs(now=now+timedelta(seconds=31))['untouched']==1
