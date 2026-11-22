"""Confirm every owned property (redesign B1: owned means confirmed).

Idempotent: already-confirmed rows are skipped. Each confirmation is attributed to an active
administrator and audited through `confirm_location`.
"""
from django.core.management.base import BaseCommand, CommandError
from apps.accounts.models import Membership
from apps.locations.models import Location
from apps.locations.service import confirm_location


def admin_actor(email=None):
    qs = Membership.objects.filter(role='admin', active=True, user__isnull=False).select_related('user')
    if email:
        qs = qs.filter(email=email.strip().lower())
    member = qs.order_by('created_at').first()
    return member.user if member else None


class Command(BaseCommand):
    help = 'Confirm all owned, unconfirmed, non-screening properties.'

    def add_arguments(self, parser):
        parser.add_argument('--actor-email', help='Active administrator to attribute the confirmations to.')
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        actor = admin_actor(options.get('actor_email'))
        if actor is None:
            raise CommandError('No active administrator found (use --actor-email with an admin account).')
        pending = list(Location.objects.filter(status=Location.Status.OWNED, confirmed=False, screening=False)
            .order_by('name').values_list('pk', 'version', 'name'))
        if options['dry_run']:
            self.stdout.write(f'Would confirm {len(pending)} owned properties.')
            return
        for pk, version, _ in pending:
            confirm_location(location_id=pk, expected_version=version, actor=actor)
        self.stdout.write(self.style.SUCCESS(f'Confirmed {len(pending)} owned properties.'))
