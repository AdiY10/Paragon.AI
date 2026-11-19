import uuid
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand,CommandError
from django.core.validators import validate_email
from django.db import transaction
from apps.accounts.models import Membership,AccessAuditEvent


@transaction.atomic
def configure_password(*,email,password,role=None,reactivate=False):
    email=email.strip().lower()
    try:validate_email(email)
    except ValidationError:raise CommandError('A valid email is required.') from None
    if not 14<=len(password)<=1024:raise CommandError('Use a password between 14 and 1024 characters.')
    member=Membership.objects.select_for_update().filter(email=email).first()
    if member and not member.active and not reactivate:raise CommandError('Membership is revoked; use --reactivate explicitly if access should return.')
    if member and role and member.role!=role:raise CommandError('Change existing roles through the administrator API; password setup does not change roles.')
    user=member.user if member and member.user_id else None
    if not user:
        matches=list(get_user_model().objects.filter(email__iexact=email)[:2])
        if len(matches)>1:raise CommandError('Ambiguous existing email; resolve the account mapping first.')
        user=matches[0] if matches else get_user_model()(username='access-'+uuid.uuid4().hex,email=email)
    try:validate_password(password,user=user)
    except ValidationError as exc:raise CommandError(' '.join(exc.messages)) from None
    if not user.is_active:raise CommandError('The account is disabled; password rotation does not reactivate it.')
    changed=not user.has_usable_password() or not user.check_password(password)
    if changed:user.set_password(password);user.save()
    elif user.pk is None:user.save()
    if not member:member=Membership(email=email,user=user,role=role or 'member')
    member.user=user
    if reactivate:member.active=True
    member.save()
    AccessAuditEvent.objects.create(actor=None,membership=member,action='password_rotated' if changed else 'password_retained',after={'method':'password','active':member.active})
