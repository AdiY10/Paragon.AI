from django.core.management.base import BaseCommand
from apps.locations.models import Location
from apps.demographics.service import compute_for_location, DemographicsUnavailable, current_result


class Command(BaseCommand):
    help = 'Compute ring demographics for one location or all non-archived placed locations.'

    def add_arguments(self, parser):
        parser.add_argument('--location', help='Location UUID or seed id (e.g. P03)')
        parser.add_argument('--force', action='store_true', help='Recompute even if a current result exists')

    def handle(self, *args, **options):
        qs = Location.objects.exclude(status='archived').select_related('current_revision')
        if options['location']:
            key = options['location']
            qs = qs.filter(seed_id=key) if len(key) == 3 else qs.filter(pk=key)
        ok = failed = skipped = 0
        for location in qs:
            if not options['force'] and current_result(location):
                skipped += 1
                continue
            try:
                result = compute_for_location(location.pk)
            except DemographicsUnavailable as exc:
                failed += 1
                self.stdout.write(f'{location.name}: unavailable ({exc.code}) {exc.message}')
                continue
            ok += 1
            pops = ', '.join(f"{r['radius_miles']} mi: {r['metrics']['population']['value'] or 0:,.0f}" for r in result.rings)
            self.stdout.write(f'{location.name}: {pops}')
        self.stdout.write(f'Computed {ok}; unavailable {failed}; already current {skipped}.')
