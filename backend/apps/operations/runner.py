from dataclasses import dataclass
from datetime import timedelta
import logging
import uuid
from django.db import transaction
from django.utils import timezone
from .contracts import JobFailure,JobResult,RetryableExecutionError
from .models import JobRun
from .registry import REGISTRY

log=logging.getLogger(__name__)

@dataclass(frozen=True)
class JobContext:
    job_id: uuid.UUID
    attempt_token: uuid.UUID
    lease_seconds: int=600
    def heartbeat(self):
        """Renew the lease; a fenced (recovered) attempt stops here instead of running twice."""
        now=timezone.now()
        updated=JobRun.objects.filter(pk=self.job_id,attempt_token=self.attempt_token,
            status=JobRun.Status.RUNNING).update(heartbeat_at=now,lease_expires_at=now+timedelta(seconds=self.lease_seconds))
        if not updated:
            raise JobFailure('SOURCE_ERROR',retryable=False)


def execute_job(job_id):
    with transaction.atomic():
        job=JobRun.objects.select_for_update().get(pk=job_id)
        if job.status in (JobRun.Status.SUCCEEDED,JobRun.Status.FAILED):
            return {'status':job.status,'records':job.records}
        now=timezone.now()
        if job.status==JobRun.Status.RUNNING and job.lease_expires_at and job.lease_expires_at>now:
            raise RetryableExecutionError('Job attempt is already leased')
        if job.next_attempt_at and job.next_attempt_at>now:
            raise RetryableExecutionError('Job retry is not due')
        spec=REGISTRY.get(job.kind)
        if spec is None or job.queue!=spec.queue or set(job.parameters)!=spec.parameter_keys:
            job.status=JobRun.Status.FAILED;job.error_code='INVALID_JOB';job.finished_at=now;job.save()
            return {'status':job.status}
        if job.attempts>=job.max_attempts:
            job.status=JobRun.Status.FAILED;job.finished_at=now;job.save()
            return {'status':job.status}
        job.attempts+=1;job.attempt_token=uuid.uuid4()
        job.status=JobRun.Status.RUNNING;job.started_at=now;job.heartbeat_at=now
        job.lease_expires_at=now+timedelta(seconds=spec.lease_seconds)
        job.next_attempt_at=None;job.error_code='';job.save()
        token=job.attempt_token
    context=JobContext(job.id,token,spec.lease_seconds)
    error=None
    try:
        result=spec.handler(context,job.parameters)
        if (not isinstance(result,JobResult) or type(result.records) is not int or result.records<0
                or type(result.failed) is not int or result.failed<0 or not isinstance(result.detail,dict)):
            raise JobFailure('SCHEMA_ERROR',retryable=False)
    except JobFailure as exc:
        log.warning('job %s (%s) failed: %s',job.id,job.kind,exc.code)
        error=exc
    except Exception:
        log.exception('job %s (%s) raised an unexpected error',job.id,job.kind)
        error=JobFailure('SOURCE_ERROR')
    with transaction.atomic():
        current=JobRun.objects.select_for_update().get(pk=job.id)
        if current.attempt_token!=token or current.status!=JobRun.Status.RUNNING:
            raise RetryableExecutionError('Job attempt lease changed')
        current.lease_expires_at=None;current.heartbeat_at=timezone.now()
        if error:
            current.error_code=error.code
            if error.retryable and current.attempts<current.max_attempts:
                current.status=JobRun.Status.RETRYING
                current.next_attempt_at=timezone.now()+timedelta(seconds=10*2**(current.attempts-1))
            else:
                current.status=JobRun.Status.FAILED;current.finished_at=timezone.now()
        else:
            current.status=JobRun.Status.SUCCEEDED;current.finished_at=timezone.now()
            current.records=result.records
            current.failed_items=result.failed
            current.detail=dict(list(result.detail.items())[:50])
        current.save()
    _alert_on_outcome(current)
    if current.status==JobRun.Status.RETRYING:
        raise RetryableExecutionError('Job failed; a bounded retry is pending') from None
    return {'status':current.status,'records':current.records}


def _alert_on_outcome(job):
    """Alert after two consecutive terminal failures of a kind, or a partial failure of at least max(2, 20%)."""
    from .alerts import raise_alert,resolve_alert
    try:
        failing_key=f'job:{job.kind}:failing'
        if job.status==JobRun.Status.FAILED:
            previous=(JobRun.objects.filter(kind=job.kind,status__in=[JobRun.Status.SUCCEEDED,JobRun.Status.FAILED],
                finished_at__lt=job.finished_at).exclude(pk=job.pk).order_by('-finished_at').first())
            if previous is not None and previous.status==JobRun.Status.FAILED:
                raise_alert(failing_key,f'{job.kind.replace("_"," ")} failed twice in a row ({job.error_code})')
        elif job.status==JobRun.Status.SUCCEEDED:
            resolve_alert(failing_key)
            partial_key=f'job:{job.kind}:partial'
            total=job.records+job.failed_items
            if job.failed_items>=max(2,0.2*total) and total:
                raise_alert(partial_key,f'{job.kind.replace("_"," ")}: {job.failed_items} of {total} items failed')
            else:
                resolve_alert(partial_key)
    except Exception:
        log.exception('alert bookkeeping failed for job %s',job.id)
