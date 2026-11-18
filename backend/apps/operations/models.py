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
    rerun_of=models.ForeignKey('self',null=True,blank=True,on_delete=models.PROTECT,related_name='reruns')
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
    recovery_count=models.PositiveSmallIntegerField(default=0)
    last_recovered_at=models.DateTimeField(null=True)
    records=models.PositiveBigIntegerField(default=0)
    error_code=models.CharField(max_length=32,blank=True)
    class Meta:
        ordering=['-created_at','id']
        constraints=[models.UniqueConstraint(fields=['kind','scope','dedup_key'],name='job_run_dedup_unique')]


class JobSchedule(models.Model):
    name=models.CharField(primary_key=True,max_length=64)
    kind=models.CharField(max_length=64)
    scope=models.CharField(max_length=160,default='global')
    calendar=models.JSONField()
    enabled=models.BooleanField(default=False)
    next_due_at=models.DateTimeField()
    last_dispatched_at=models.DateTimeField(null=True)
    updated_at=models.DateTimeField(auto_now=True)
    class Meta:
        ordering=['name']


class ScheduleOccurrence(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    schedule=models.ForeignKey(JobSchedule,on_delete=models.PROTECT,related_name='occurrences')
    local_date=models.DateField()
    scheduled_for=models.DateTimeField()
    dispatched_at=models.DateTimeField()
    missed_count=models.PositiveIntegerField(default=0)
    delay_seconds=models.PositiveIntegerField()
    calendar_at_dispatch=models.JSONField()
    job=models.OneToOneField(JobRun,on_delete=models.PROTECT,related_name='scheduled_occurrence')
    class Meta:
        constraints=[models.UniqueConstraint(fields=['schedule','local_date'],name='schedule_local_date_unique')]
        ordering=['-scheduled_for']


class SchedulerState(models.Model):
    name=models.CharField(primary_key=True,max_length=32,default='primary')
    owner=models.UUIDField(null=True)
    lease_until=models.DateTimeField()
    last_tick_at=models.DateTimeField(null=True)


class JobRecoveryEvent(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    job=models.ForeignKey(JobRun,on_delete=models.PROTECT,related_name='recovery_events')
    reason=models.CharField(max_length=32)
    outcome=models.CharField(max_length=16)
    recorded_at=models.DateTimeField()
    previous_task_id=models.CharField(max_length=64,blank=True)
    replacement_task_id=models.CharField(max_length=64,blank=True)
    class Meta:
        ordering=['recorded_at','id']
