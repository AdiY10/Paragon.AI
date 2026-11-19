import uuid
from django.db import models
from apps.sources.models import ImmutableQuerySet


class AreaSection(models.Model):
    """Immutable result for one profile section (economy, traffic, hazards) at one pin.

    Valid while ``analysis_version`` matches the location; recomputation adds a row.
    """
    SECTIONS = [('economy', 'Economy'), ('traffic', 'Traffic'), ('hazards', 'Hazards'), ('businesses', 'Businesses'), ('jobs', 'Jobs')]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    location = models.ForeignKey('locations.Location', on_delete=models.PROTECT, related_name='area_sections')
    revision = models.ForeignKey('locations.LocationRevision', on_delete=models.PROTECT, related_name='+')
    analysis_version = models.PositiveIntegerField()
    section = models.CharField(max_length=16, choices=SECTIONS)
    status = models.CharField(max_length=16, choices=[('available', 'Available'), ('unavailable', 'Unavailable')])
    data = models.JSONField()
    sources = models.JSONField()
    snapshot_ids = models.JSONField(default=list)
    inputs_sha256 = models.CharField(max_length=64)
    computed_at = models.DateTimeField(auto_now_add=True)
    objects = ImmutableQuerySet.as_manager()

    class Meta:
        ordering = ['-computed_at', 'id']
        constraints = [models.UniqueConstraint(fields=['location', 'analysis_version', 'section', 'inputs_sha256'],
            name='area_section_unique')]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValueError('Area section results are immutable')
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError('Area section results cannot be deleted')
