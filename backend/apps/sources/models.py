import uuid
from django.db import models


class SourceDefinition(models.Model):
    id = models.CharField(primary_key=True, max_length=6)
    name = models.CharField(max_length=160)
    provider = models.CharField(max_length=160)
    purpose = models.TextField()
    coverage = models.TextField()
    documentation_url = models.URLField()
    licence = models.TextField()
    attribution = models.TextField()
    cadence = models.CharField(max_length=32)
    stale_after_days = models.PositiveSmallIntegerField(null=True, blank=True)
    privacy_note = models.TextField()
    adapter_version = models.CharField(max_length=32, default='unimplemented')
    catalog_version = models.PositiveIntegerField()

    class Meta:
        ordering = ['id']
        constraints = [models.CheckConstraint(condition=models.Q(id__regex=r'^SRC-\d{2}$'), name='source_identifier_valid')]


class ImmutableQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValueError('Published source records are immutable')
    def delete(self):
        raise ValueError('Published source records cannot be deleted')
    def bulk_update(self, objs, fields, batch_size=None):
        raise ValueError('Published source records are immutable')
    def bulk_create(self, objs, *args, **kwargs):
        if kwargs.get('update_conflicts'):
            raise ValueError('Published source records are immutable')
        return super().bulk_create(objs, *args, **kwargs)


class SourceSnapshot(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    source = models.ForeignKey(SourceDefinition, on_delete=models.PROTECT, related_name='snapshots')
    scope = models.CharField(max_length=160)
    release = models.CharField(max_length=96)
    data_period = models.CharField(max_length=160)
    source_url = models.CharField(max_length=2048)
    retrieved_at = models.DateTimeField()
    published_at = models.DateTimeField(auto_now_add=True)
    adapter_version = models.CharField(max_length=64)
    source_schema = models.JSONField()
    context = models.JSONField(default=dict)
    record_count = models.PositiveIntegerField()
    artifact_key = models.CharField(max_length=80)
    sha256 = models.CharField(max_length=64)
    size_bytes = models.PositiveBigIntegerField()
    objects = ImmutableQuerySet.as_manager()

    class Meta:
        ordering = ['-published_at', 'id']
        constraints = [models.UniqueConstraint(fields=['source','scope','release','sha256','adapter_version'], name='source_snapshot_content_unique')]
        indexes = [models.Index(fields=['source','scope','release']), models.Index(fields=['source','release']),
            models.Index(fields=['source','scope','retrieved_at'])]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValueError('Published source records are immutable')
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError('Published source records cannot be deleted')


class SourceCheck(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    source = models.ForeignKey(SourceDefinition, on_delete=models.PROTECT, related_name='checks')
    scope = models.CharField(max_length=160)
    run_key = models.CharField(max_length=160)
    completed_at = models.DateTimeField()
    succeeded = models.BooleanField()
    error_code = models.CharField(max_length=32, blank=True)
    snapshot = models.ForeignKey(SourceSnapshot, null=True, blank=True, on_delete=models.PROTECT)
    objects = ImmutableQuerySet.as_manager()

    class Meta:
        constraints = [models.UniqueConstraint(fields=['source','scope','run_key'], name='source_check_run_unique')]
        ordering = ['-completed_at', 'id']

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValueError('Source check history is immutable')
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError('Source check history cannot be deleted')


class SourceHealth(models.Model):
    source = models.ForeignKey(SourceDefinition, on_delete=models.PROTECT, related_name='health_scopes')
    scope = models.CharField(max_length=160)
    last_checked_at = models.DateTimeField(null=True)
    last_success_at = models.DateTimeField(null=True)
    consecutive_failures = models.PositiveIntegerField(default=0)
    error_code = models.CharField(max_length=32, blank=True)
    latest_snapshot = models.ForeignKey(SourceSnapshot, null=True, on_delete=models.PROTECT)
    available_release = models.CharField(max_length=96, blank=True)
    available_since = models.DateTimeField(null=True)
    processed_release = models.CharField(max_length=96, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['source','scope'], name='source_health_scope_unique')]
        ordering = ['scope']
