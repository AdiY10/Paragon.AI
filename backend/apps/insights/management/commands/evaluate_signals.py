from django.core.management.base import BaseCommand
from apps.locations.models import Location
from apps.insights.signals import evaluate


class Command(BaseCommand):
    help = 'Re-evaluate signals for all non-archived locations from stored results (baseline or after threshold edits).'

    def handle(self, *args, **options):
        totals = [0, 0, 0]
        for location in Location.objects.exclude(status='archived'):
            for i, n in enumerate(evaluate(location)):
                totals[i] += n
        self.stdout.write(f'Signals created {totals[0]}, updated {totals[1]}, resolved {totals[2]}.')
