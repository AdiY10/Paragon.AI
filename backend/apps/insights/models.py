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
    reviewed_at = models.DateTimeField(null=True, blank=True)
    # "Was this useful?" from the reviewer: tunes thresholds later (R2 item 20).
    feedback = models.CharField(max_length=12, blank=True, choices=[('useful', 'Useful'), ('not_useful', 'Not useful')])
    # Evidence when the current episode began, and how many times the condition has (re)appeared.
    first_evidence = models.JSONField(default=dict, blank=True)
    episode = models.PositiveIntegerField(default=1)
    episode_started_at = models.DateTimeField(null=True, blank=True)

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
    resolved = models.JSONField(default=list, blank=True)
    sources_updated = models.JSONField(default=list)
    stats = models.JSONField(default=dict)

    class Meta:
        ordering = ['-generated_at']

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValueError('Briefs are immutable')
        super().save(*args, **kwargs)


class TenantFiler(models.Model):
    """An admin-confirmed mapping from a tenant (brand) to an SEC filer (FR-22). Never auto-applied."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.OneToOneField('locations.Tenant', on_delete=models.CASCADE, related_name='sec_filer')
    cik = models.CharField(max_length=10)
    company_name = models.CharField(max_length=200)
    mapped_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+')
    mapped_at = models.DateTimeField(auto_now_add=True)


class LocationMetrics(models.Model):
    """Per-location snapshot of comparable values and attention (R2 item 13).

    Derived, not a source of truth: rebuilt after every evaluation or review and ignored
    when its analysis_version is behind the location's, so lists and comparisons read one
    row per property instead of re-deriving everything.
    """
    location = models.OneToOneField('locations.Location', on_delete=models.CASCADE, primary_key=True,
        related_name='metrics_snapshot')
    analysis_version = models.PositiveIntegerField()
    values = models.JSONField(default=dict)
    attention = models.CharField(max_length=8, default='Clear')
    updated_at = models.DateTimeField(auto_now=True)
