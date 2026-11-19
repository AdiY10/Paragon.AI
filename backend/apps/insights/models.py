import uuid
from django.conf import settings
from django.db import models


class Signal(models.Model):
    """A deterministic change signal (docs/04 §5). One row per (location, rule, subject)."""
    SEVERITIES = [('High', 'High'), ('Watch', 'Watch'), ('FYI', 'FYI')]
    STATUSES = [('active', 'Active'), ('resolved', 'Resolved'), ('expired', 'Expired'), ('dismissed', 'Dismissed')]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    location = models.ForeignKey('locations.Location', on_delete=models.PROTECT, related_name='signals')
    rule_id = models.CharField(max_length=8)
    subject = models.CharField(max_length=200)
    category = models.CharField(max_length=32)
    severity = models.CharField(max_length=8, choices=SEVERITIES)
    direction = models.CharField(max_length=10, choices=[('positive', 'Positive'), ('negative', 'Negative'), ('neutral', 'Neutral')])
    title = models.CharField(max_length=300)
    why = models.TextField()
    evidence = models.JSONField(default=dict)
    period = models.CharField(max_length=120, blank=True)
    source = models.CharField(max_length=8, blank=True)
    event_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUSES, default='active')
    resolved_reason = models.CharField(max_length=120, blank=True)
    first_detected_at = models.DateTimeField(auto_now_add=True)
    last_changed_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(auto_now_add=True)
    analysis_version = models.PositiveIntegerField()
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    review_note = models.TextField(blank=True)

    class Meta:
        ordering = ['-last_changed_at', 'id']
        constraints = [models.UniqueConstraint(fields=['location', 'rule_id', 'subject'], name='signal_identity_unique')]
        indexes = [models.Index(fields=['status', 'severity']), models.Index(fields=['location', 'status'])]


class Brief(models.Model):
    """Immutable This Week brief (FR-21)."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    kind = models.CharField(max_length=10, choices=[('baseline', 'Baseline'), ('weekly', 'Weekly'), ('manual', 'Manual')])
    title = models.CharField(max_length=200)
    generated_at = models.DateTimeField(auto_now_add=True)
    since = models.DateTimeField(null=True, blank=True)
    items = models.JSONField(default=list)
    fyi = models.JSONField(default=list)
    sources_updated = models.JSONField(default=list)
    stats = models.JSONField(default=dict)

    class Meta:
        ordering = ['-generated_at']

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValueError('Briefs are immutable')
        super().save(*args, **kwargs)
