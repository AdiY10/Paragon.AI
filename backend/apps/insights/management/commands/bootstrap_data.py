"""One-command data bootstrap for a fresh deployment (T11). Safe to re-run: every step is idempotent."""
from pathlib import Path
from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = ('Sync catalog and schedules, import the public seed and listing tenants, ingest ACS (2024 and 2019 '
            'baseline), import archived Overture captures, compute every section, evaluate signals and generate '
            'the baseline brief.')

    def add_arguments(self, parser):
        parser.add_argument('--overture-archive', type=Path, help='Directory of archived Overture captures (optional)')
        parser.add_argument('--skip-compute', action='store_true')

    def handle(self, *args, **options):
        from django.conf import settings
        from apps.locations.seeding import import_public_portfolio
        from apps.insights.brief import generate
        from apps.insights.models import Brief
        step = lambda msg: self.stdout.write(self.style.MIGRATE_HEADING(msg))
        step('1/8 Source catalog and schedules')
        call_command('sync_sources')
        call_command('sync_schedules', enable_available=True)
        step('2/8 Public portfolio seed (unconfirmed)')
        import_public_portfolio()
        step('3/8 Listing tenants (unconfirmed claims)')
        call_command('import_listing_tenants')
        step('4/8 ACS 2020-2024 for portfolio states and neighbours')
        call_command('ingest_acs', year=2024)
        step('5/8 ACS 2015-2019 trend baseline')
        call_command('ingest_acs', year=2019)
        if options['overture_archive']:
            step('6/8 Archived Overture captures')
            call_command('import_overture_captures', directory=options['overture_archive'],
                store_root=Path(settings.SOURCE_ARTIFACT_ROOT))
            call_command('compact_overture')
        else:
            step('6/8 No Overture archive given; captures will be taken on demand (history starts now)')
        if not options['skip_compute']:
            step('7/8 Demographics and area sections for every pinned location (several minutes)')
            call_command('compute_ring_demographics')
            call_command('compute_area_profile')
        step('8/8 Signals and baseline brief')
        call_command('evaluate_signals')
        if not Brief.objects.exists():
            self.stdout.write(generate().title)
        self.stdout.write(self.style.SUCCESS('Bootstrap complete.'))
