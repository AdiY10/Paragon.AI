from django.db import transaction
from django.core.management.base import BaseCommand, CommandError
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from apps.accounts.models import Membership, AccessAuditEvent

class Command(BaseCommand):
    help = 'Create the initial admin invitation without a password or an auth bypass.'
    def add_arguments(self, parser):
        parser.add_argument('email')
    @transaction.atomic
    def handle(self, *args, **options):
        email = options['email'].strip().lower()
        try:
            validate_email(email)
        except ValidationError as exc:
            raise CommandError('A valid email is required.') from exc
        member, created = Membership.objects.get_or_create(email=email, defaults={'role': 'admin'})
        if not created:
            raise CommandError('Membership already exists; no role or access was changed.')
        AccessAuditEvent.objects.create(membership=member, action='bootstrap_invited',
            after={'email': member.email, 'role': member.role, 'active': True})
        self.stdout.write(self.style.SUCCESS('Initial administrator invited. Use the configured OIDC sign-in.'))
