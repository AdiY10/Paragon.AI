from datetime import timedelta
from unittest.mock import patch
import pytest
from django.utils import timezone
from django_q.models import OrmQ
from apps.operations.models import JobRun
from apps.operations.service import enqueue_job
from apps.operations.runner import execute_job
from apps.operations.contracts import JobFailure,RetryableExecutionError

pytestmark=pytest.mark.django_db


def submit(key='baseline'):
    return enqueue_job(kind='sync_source_catalog',scope='global',dedup_key=key)


def test_submission_is_durable_and_deduplicated():
    job,created=submit()
    assert created and job.status=='queued'
    assert job.transport_task_id
    assert OrmQ.objects.count()==1
    again,created=submit()
    assert not created and again.id==job.id
    assert OrmQ.objects.count()==1


def test_transport_enqueue_failure_rolls_back_job():
    from django_q.tasks import async_task as real_enqueue
    def enqueue_then_fail(*args,**kwargs):
        real_enqueue(*args,**kwargs)
        raise OSError('transport confirmation failed')
    with patch('apps.operations.service.async_task',side_effect=enqueue_then_fail):
        with pytest.raises(OSError):submit()
    assert JobRun.objects.count()==0
    assert OrmQ.objects.count()==0


def test_execution_is_idempotent_after_success():
    job,_=submit()
    assert execute_job(job.id)=={'status':'succeeded','records':16}
    assert execute_job(job.id)=={'status':'succeeded','records':16}
    job.refresh_from_db()
    assert job.attempts==1 and job.finished_at and job.heartbeat_at


def test_retry_is_bounded_and_error_details_are_sanitized():
    job,_=submit()
    with patch('apps.operations.registry.sync_catalog',side_effect=OSError('private address and token=secret')):
        for attempt in range(1,4):
            if attempt<3:
                with pytest.raises(RetryableExecutionError,match='bounded retry') as caught:
                    execute_job(job.id)
                assert 'secret' not in str(caught.value)
            else:
                assert execute_job(job.id)['status']=='failed'
            job.refresh_from_db()
            assert job.attempts==attempt and job.error_code=='SOURCE_ERROR'
            JobRun.objects.filter(pk=job.pk).update(next_attempt_at=timezone.now()-timedelta(seconds=1))
    assert execute_job(job.id)['status']=='failed'
    job.refresh_from_db();assert job.attempts==3


def test_active_lease_is_not_executed_twice():
    job,_=submit()
    JobRun.objects.filter(pk=job.pk).update(status='running',lease_expires_at=timezone.now()+timedelta(minutes=1))
    with pytest.raises(RetryableExecutionError,match='leased'):execute_job(job.id)
    job.refresh_from_db();assert job.attempts==0


def test_expired_lease_can_be_reclaimed():
    job,_=submit()
    JobRun.objects.filter(pk=job.pk).update(status='running',lease_expires_at=timezone.now()-timedelta(seconds=1))
    assert execute_job(job.id)['status']=='succeeded'


def test_nonretryable_failure_is_terminal():
    job,_=submit()
    with patch('apps.operations.registry.sync_catalog',side_effect=JobFailure('NOT_CONFIGURED',retryable=False)):
        assert execute_job(job.id)['status']=='failed'
    job.refresh_from_db();assert job.attempts==1


def test_unknown_handlers_and_unexpected_parameters_are_rejected():
    with pytest.raises(ValueError,match='Unknown job'):
        enqueue_job(kind='os.system',scope='global',dedup_key='bad')
    with pytest.raises(ValueError,match='parameters'):
        enqueue_job(kind='sync_source_catalog',scope='global',dedup_key='bad',parameters={'secret':'no'})
    assert not JobRun.objects.exists()


def test_transport_receipt_can_be_redelivered_after_worker_loss():
    from django_q.brokers import get_broker
    job,_=submit()
    broker=get_broker('paragon-maintenance')
    first=broker.dequeue()
    assert len(first)==1
    assert broker.dequeue()==None
    OrmQ.objects.filter(pk=first[0][0]).update(lock=timezone.now()-timedelta(seconds=1))
    second=broker.dequeue()
    assert second==first
    assert JobRun.objects.get(pk=job.pk).status=='queued'
    broker.acknowledge(second[0][0])
    assert OrmQ.objects.count()==0


@pytest.mark.django_db(transaction=True)
def test_concurrent_submissions_create_one_job_and_one_transport_message():
    from concurrent.futures import ThreadPoolExecutor
    from django.db import connection,connections
    if connection.vendor!='postgresql':
        pytest.skip('Concurrent row-lock behavior requires PostgreSQL')
    def enqueue(_):
        try:
            job,created=submit('concurrent')
            return job.id,created
        finally:
            connections.close_all()
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(enqueue,range(2)))
    assert len({r[0] for r in results})==1
    assert sum(r[1] for r in results)==1
    assert JobRun.objects.count()==1 and OrmQ.objects.count()==1


def test_old_attempt_cannot_overwrite_new_attempt_state():
    import uuid
    job,_=submit()
    def simulate_new_attempt():
        JobRun.objects.filter(pk=job.pk).update(attempt_token=uuid.uuid4())
        return 16
    with patch('apps.operations.registry.sync_catalog',side_effect=simulate_new_attempt):
        with pytest.raises(RetryableExecutionError,match='lease changed'):
            execute_job(job.id)
    job.refresh_from_db()
    assert job.status=='running' and job.records==0
