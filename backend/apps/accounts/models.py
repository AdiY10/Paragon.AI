import uuid
from django.conf import settings
from django.db import models
from django.db.models.functions import Lower


class Membership(models.Model):
    class Role(models.TextChoices):
        ADMIN = 'admin', 'Admin'
        MEMBER = 'member', 'Member'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField()
    user = models.OneToOneField(settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='membership')
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.MEMBER)
    active = models.BooleanField(default=True)
    invited_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='issued_invitations')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    # Last request by this person (updated at most every 10 minutes) for the Admin sign-in log.
    last_seen_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(Lower('email'), name='membership_email_unique'),
            models.CheckConstraint(condition=models.Q(role__in=['admin', 'member']), name='membership_role_valid')]

    def save(self, *args, **kwargs):
        self.email = self.email.strip().lower()
        super().save(*args, **kwargs)


class AccessAuditEvent(models.Model):
    """Append-only application records for changes to access and roles."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='access_audit_events')
    membership = models.ForeignKey(Membership, on_delete=models.PROTECT, related_name='audit_events')
    action = models.CharField(max_length=32)
    before = models.JSONField(default=dict)
    after = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)


class LoginThrottle(models.Model):
    """HMAC identifiers only; no submitted password, address, or email is retained."""
    key=models.CharField(primary_key=True,max_length=64)
    window_start=models.DateTimeField()
    attempts=models.PositiveIntegerField(default=0)
