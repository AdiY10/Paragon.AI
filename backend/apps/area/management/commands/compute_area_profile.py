from django.core.management.base import BaseCommand
from apps.locations.models import Location
from apps.area.service import compute_area, SECTIONS
from apps.area.http import SourceError


class Command(BaseCommand):
    help = 'Compute economy, traffic and hazard sections for one or all placed, non-archived locations.'

    def add_arguments(self, parser):
        parser.add_argument('--location', help='Location UUID or seed id (e.g. P20)')
        parser.add_argument('--section', choices=SECTIONS, action='append')

    def handle(self, *args, **options):
        qs = Location.objects.exclude(status='archived').select_related('current_revision')
        if key := options['location']:
            qs = qs.filter(seed_id=key) if len(key) == 3 else qs.filter(pk=key)
        for location in qs:
            if location.current_revision is None or location.current_revision.lat is None:
                self.stdout.write(f'{location.name}: no pin; skipped')
                continue
            try:
                rows = compute_area(location.pk, sections=options['section'] or SECTIONS)
            except SourceError as exc:
                self.stdout.write(f'{location.name}: {exc.code}')
                continue
            self.stdout.write(f"{location.name}: " + ', '.join(f'{r.section} {r.status}' for r in rows))
