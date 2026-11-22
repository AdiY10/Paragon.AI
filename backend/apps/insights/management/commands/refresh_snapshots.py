"""Rebuild every location's metrics snapshot (after a deploy that changes what it holds)."""
from django.core.management.base import BaseCommand
from apps.insights.metrics import refresh_snapshot
from apps.locations.models import Location


class Command(BaseCommand):
    help = 'Rebuild the LocationMetrics snapshot for every non-archived location.'

    def handle(self, *args, **options):
        n = 0
        for location in Location.objects.exclude(status='archived').select_related('current_revision'):
            refresh_snapshot(location)
            n += 1
        self.stdout.write(f'Rebuilt {n} snapshots.')
