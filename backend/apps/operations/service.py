from django.db import transaction
from django_q.tasks import async_task
from .models import JobRun
from .registry import REGISTRY

@transaction.atomic
def enqueue_job(*,kind,scope,dedup_key,parameters=None,requested_by=None,rerun_of=None):
    if kind not in REGISTRY:
        raise ValueError('Unknown job kind')
    spec=REGISTRY[kind]
    parameters=dict(parameters or {})
    if set(parameters)!=spec.parameter_keys:
        raise ValueError('Unexpected or missing job parameters')
    if not isinstance(scope,str) or not scope.strip() or len(scope)>160 or not isinstance(dedup_key,str) or not dedup_key.strip() or len(dedup_key)>160:
        raise ValueError('Invalid job scope or deduplication key')
    job,created=JobRun.objects.get_or_create(kind=kind,scope=scope,dedup_key=dedup_key,
        defaults={'parameters':parameters,'queue':spec.queue,'requested_by':requested_by,'rerun_of':rerun_of})
    if not created:
        if job.parameters!=parameters or job.rerun_of_id!=getattr(rerun_of,'id',None):
            raise ValueError('Deduplicated job has different parameters')
        return job,False
    job.transport_task_id=async_task('apps.operations.runner.execute_job',str(job.id),
        cluster=spec.queue,timeout=spec.timeout_seconds)
    job.save(update_fields=['transport_task_id'])
    return job,True
