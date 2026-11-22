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
    # apps.area.service.SECTION_LOGIC at compute time; the analysis sweep recomputes older rows.
    logic_version = models.PositiveSmallIntegerField(default=1)
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


class OvertureCapture(models.Model):
    """A compact Overture places capture for one pin and release (R2 item 14).

    Gzipped JSON lines with only the fields the product uses (no per-record ``sources``),
    about 1/40th of the raw size, so a 3-mile capture loads in a few MB of memory. The
    summary (1-mile count and brand counts) is written once, at capture time, for the
    release-pair guard.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    release = models.CharField(max_length=32)
    pin_key = models.CharField(max_length=40)
    radius_miles = models.FloatField(default=3)
    compact_key = models.CharField(max_length=100)
    record_count = models.PositiveIntegerField()
    summary = models.JSONField(default=dict)
    raw_snapshot = models.ForeignKey('sources.SourceSnapshot', null=True, blank=True, on_delete=models.PROTECT,
        related_name='+')
    raw_pruned = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['release', 'pin_key'], name='overture_capture_unique')]
        indexes = [models.Index(fields=['release'])]


class OvertureReleasePair(models.Model):
    """Portfolio-wide comparison of two releases, computed once all pins are captured.

    ``broad_change``: counts moved >15% at 30%+ of pins (a data change, not the market).
    ``brand_drops``: brands that lost at least half their captured locations at once.
    """
    prior = models.CharField(max_length=32)
    latest = models.CharField(max_length=32)
    broad_change = models.BooleanField(null=True)
    cohort_size = models.PositiveIntegerField(default=0)
    brand_drops = models.JSONField(default=list)
    computed_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['prior', 'latest'], name='overture_pair_unique')]
