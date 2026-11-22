"""Import an exported Overture history (redesign B2; run on production)."""
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from apps.area.overture_store import HistoryError, import_history
from apps.sources.storage import LocalArtifactStore


class Command(BaseCommand):
    help = 'Verify and import compact Overture captures; existing release/pin pairs are kept.'

    def add_arguments(self, parser):
        parser.add_argument('path', help='The .tar written by export_overture_history')

    def handle(self, *args, path, **options):
        try:
            created, skipped = import_history(path, LocalArtifactStore(settings.SOURCE_ARTIFACT_ROOT))
        except (HistoryError, KeyError, OSError) as exc:
            raise CommandError(f'Import failed: {exc}') from exc
        self.stdout.write(f'Imported {created} captures ({skipped} already present); release pairs recomputed.')
