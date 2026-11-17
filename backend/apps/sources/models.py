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
    record_count = models.PositiveIntegerField()
    artifact_key = models.CharField(max_length=80)
    sha256 = models.CharField(max_length=64)
    size_bytes = models.PositiveBigIntegerField()
    objects = ImmutableQuerySet.as_manager()

    class Meta:
        ordering = ['-published_at', 'id']
        constraints = [models.UniqueConstraint(fields=['source','scope','release','sha256','adapter_version'], name='source_snapshot_content_unique')]
        indexes = [models.Index(fields=['source','scope','release'])]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValueError('Published source records are immutable')
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError('Published source records cannot be deleted')
