"""Export the captured Overture history for owned properties (redesign B2; run on the preview)."""
from django.conf import settings
from django.core.management.base import BaseCommand
from apps.area.overture_store import export_history
from apps.locations.models import Location
from apps.sources.storage import LocalArtifactStore


class Command(BaseCommand):
    help = 'Write a tar of compact Overture captures (owned pins only) plus a checksummed manifest.'

    def add_arguments(self, parser):
        parser.add_argument('out', help='Path of the .tar to write')

    def handle(self, *args, out, **options):
        owned = Location.objects.filter(status='owned', screening=False).select_related('current_revision')
        n = export_history(list(owned), LocalArtifactStore(settings.SOURCE_ARTIFACT_ROOT), out)
        self.stdout.write(f'Exported {n} captures to {out}.')
