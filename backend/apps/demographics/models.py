import uuid
from django.db import models
from apps.sources.models import ImmutableQuerySet


class RingDemographics(models.Model):
    """Immutable ring demographics for one location pin, ring preset and ACS vintage.

    Valid only while ``analysis_version`` equals the location's current value;
    moving the pin or changing the ring preset makes it stale, never edited.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    location = models.ForeignKey('locations.Location', on_delete=models.PROTECT, related_name='ring_demographics')
    revision = models.ForeignKey('locations.LocationRevision', on_delete=models.PROTECT, related_name='+')
    analysis_version = models.PositiveIntegerField()
    ring_preset = models.CharField(max_length=8)
    acs_year = models.PositiveSmallIntegerField()
    data_period = models.CharField(max_length=64)
    geography_snapshot = models.ForeignKey('sources.SourceSnapshot', on_delete=models.PROTECT, related_name='+')
    acs_snapshot_ids = models.JSONField()
    rings = models.JSONField()
    computed_at = models.DateTimeField(auto_now_add=True)
    objects = ImmutableQuerySet.as_manager()

    class Meta:
        ordering = ['-computed_at', 'id']
        constraints = [models.UniqueConstraint(fields=['location', 'analysis_version', 'acs_year', 'geography_snapshot'],
            name='ring_demographics_unique')]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValueError('Ring demographic results are immutable')
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError('Ring demographic results cannot be deleted')
