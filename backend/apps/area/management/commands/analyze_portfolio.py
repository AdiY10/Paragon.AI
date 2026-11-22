"""Queue background analyses for every placed location with missing or outdated parts (redesign B3a).

Used once after a production rebuild; afterwards the scheduler sweep keeps analyses complete.
"""
from django.core.management.base import BaseCommand
from apps.area import analysis
from apps.locations.models import Location


class Command(BaseCommand):
    help = 'Queue background analyses for placed locations that are missing results.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Only report what is missing.')

    def handle(self, *args, dry_run=False, **options):
        queued = complete = 0
        for location in (Location.objects.exclude(status=Location.Status.ARCHIVED)
                .exclude(current_revision__lat__isnull=True).select_related('current_revision').order_by('name')):
            missing = analysis.missing_sections(location)
            if not missing:
                complete += 1
                continue
            self.stdout.write(f'{location.name}: {", ".join(missing)}')
            if not dry_run and analysis.ensure_analysis(location.pk, interactive=False) is not None:
                queued += 1
        self.stdout.write(f'{complete} complete, {queued} queued' + (' (dry run)' if dry_run else ''))
