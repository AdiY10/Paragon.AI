from dataclasses import dataclass
from datetime import timedelta
import uuid
from django.db import transaction
from django.utils import timezone
from .contracts import JobFailure,JobResult,RetryableExecutionError
from .models import JobRun
from .registry import REGISTRY

@dataclass(frozen=True)
class JobContext:
    job_id: uuid.UUID
    attempt_token: uuid.UUID
    def heartbeat(self):
        updated=JobRun.objects.filter(pk=self.job_id,attempt_token=self.attempt_token,
            status=JobRun.Status.RUNNING).update(heartbeat_at=timezone.now())
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
        job.lease_expires_at=now+timedelta(seconds=spec.timeout_seconds+30)
        job.next_attempt_at=None;job.error_code='';job.save()
        token=job.attempt_token
    context=JobContext(job.id,token)
    error=None
    try:
        result=spec.handler(context,job.parameters)
        if not isinstance(result,JobResult) or type(result.records) is not int or result.records<0:
            raise JobFailure('SCHEMA_ERROR',retryable=False)
    except JobFailure as exc:
        error=exc
    except Exception:
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
        current.save()
    if current.status==JobRun.Status.RETRYING:
        raise RetryableExecutionError('Job failed; a bounded retry is pending') from None
    return {'status':current.status,'records':current.records}
