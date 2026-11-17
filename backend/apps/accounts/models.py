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

    class Meta:
        constraints = [models.UniqueConstraint(Lower('email'), name='membership_email_unique'),
            models.CheckConstraint(condition=models.Q(role__in=['admin', 'member']), name='membership_role_valid')]

    def save(self, *args, **kwargs):
        self.email = self.email.strip().lower()
        super().save(*args, **kwargs)
