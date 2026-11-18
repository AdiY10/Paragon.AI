"""Recover lost transport messages and expired attempts without duplicating live work."""
from datetime import timedelta
import uuid
from django.db import transaction
from django.utils import timezone
from django_q.models import OrmQ,Task
from django_q.tasks import async_task
from .models import JobRun,JobRecoveryEvent
from .registry import REGISTRY

MAX_RECOVERIES=6


def _messages(job):
    return [message for message in OrmQ.objects.filter(key=job.queue)
        if message.task.get('id')==job.transport_task_id
        and message.task.get('func')=='apps.operations.runner.execute_job']


def recover_jobs(*,now=None,limit=100):
    now=now or timezone.now()
    if timezone.is_naive(now):raise ValueError('Recovery time must be timezone-aware')
    if type(limit) is not int or not 1<=limit<=1000:raise ValueError('Invalid recovery batch limit')
    ids=list(JobRun.objects.filter(status__in=['queued','retrying','running']).order_by('created_at').values_list('id',flat=True))
    result={'requeued':0,'released':0,'failed':0,'untouched':0}
    for job_id in ids:
        if result["requeued"]+result["released"]+result["failed"]>=limit:break
        with transaction.atomic():
            job=JobRun.objects.select_for_update().get(pk=job_id)
            if job.status in ('succeeded','failed'):
                result['untouched']+=1;continue
            if job.status=='running' and job.lease_expires_at and job.lease_expires_at>now:
                result['untouched']+=1;continue
            if job.status=='retrying' and job.next_attempt_at and job.next_attempt_at>now:
                result['untouched']+=1;continue
            if job.last_recovered_at and now-job.last_recovered_at<timedelta(seconds=30):
                result['untouched']+=1;continue
            messages=_messages(job)
            if job.status=='queued' and (messages or now-job.created_at<timedelta(seconds=30)):
                result['untouched']+=1;continue
            if job.status=='retrying' and messages:
                failures=Task.objects.filter(pk=job.transport_task_id,success=False)
                if job.last_recovered_at:
                    failures=failures.filter(stopped__gt=job.last_recovered_at)
                if any(m.lock is None or m.lock<=now for m in messages) or not failures.exists():
                    result['untouched']+=1;continue
            reason='EXPIRED_LEASE' if job.status=='running' else 'RETRY_DUE' if job.status=='retrying' else 'MISSING_MESSAGE'
            previous=job.transport_task_id
            spec=REGISTRY.get(job.kind)
            if job.attempts>=job.max_attempts or job.recovery_count>=MAX_RECOVERIES or spec is None or job.queue!=spec.queue or set(job.parameters)!=spec.parameter_keys:
                job.status='failed';job.finished_at=now;job.lease_expires_at=None
                job.attempt_token=uuid.uuid4()
                job.error_code='ATTEMPTS_EXHAUSTED' if job.attempts>=job.max_attempts else 'TRANSPORT_LOST'
                job.save()
                for message in messages:message.delete()
                JobRecoveryEvent.objects.create(job=job,reason=reason,outcome='failed',recorded_at=now,previous_task_id=previous)
                result['failed']+=1;continue
            # Fence the old attempt before making a receipt available again.
            job.attempt_token=uuid.uuid4();job.lease_expires_at=None
            job.status='retrying';job.next_attempt_at=now
            job.recovery_count+=1;job.last_recovered_at=now
            if messages:
                for message in messages:
                    OrmQ.objects.filter(pk=message.pk).update(lock=now-timedelta(microseconds=1))
                outcome='released'
            else:
                job.transport_task_id=async_task('apps.operations.runner.execute_job',str(job.id),
                    cluster=spec.queue,timeout=spec.timeout_seconds)
                outcome='requeued'
            job.save()
            JobRecoveryEvent.objects.create(job=job,reason=reason,outcome=outcome,recorded_at=now,
                previous_task_id=previous,replacement_task_id=job.transport_task_id)
            result[outcome]+=1
    return result
