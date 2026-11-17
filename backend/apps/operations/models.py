import uuid
from django.conf import settings
from django.db import models

class JobRun(models.Model):
    class Status(models.TextChoices):
        QUEUED='queued','Queued'
        RUNNING='running','Running'
        RETRYING='retrying','Retrying'
        SUCCEEDED='succeeded','Succeeded'
        FAILED='failed','Failed'
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    kind=models.CharField(max_length=64)
    scope=models.CharField(max_length=160)
    dedup_key=models.CharField(max_length=160)
    queue=models.CharField(max_length=32)
    parameters=models.JSONField(default=dict)
    status=models.CharField(max_length=16,choices=Status.choices,default=Status.QUEUED)
    requested_by=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,on_delete=models.SET_NULL)
    transport_task_id=models.CharField(max_length=64,blank=True)
    attempts=models.PositiveSmallIntegerField(default=0)
    max_attempts=models.PositiveSmallIntegerField(default=3)
    attempt_token=models.UUIDField(null=True)
    created_at=models.DateTimeField(auto_now_add=True)
    started_at=models.DateTimeField(null=True)
    finished_at=models.DateTimeField(null=True)
    heartbeat_at=models.DateTimeField(null=True)
    lease_expires_at=models.DateTimeField(null=True)
    next_attempt_at=models.DateTimeField(null=True)
    records=models.PositiveBigIntegerField(default=0)
    error_code=models.CharField(max_length=32,blank=True)
    class Meta:
        ordering=['-created_at','id']
        constraints=[models.UniqueConstraint(fields=['kind','scope','dedup_key'],name='job_run_dedup_unique')]
