from django.core.management.base import BaseCommand
from apps.sources.catalog import sync_catalog

class Command(BaseCommand):
    help = 'Synchronize documented source metadata without claiming data ingestion.'
    def handle(self, *args, **options):
        self.stdout.write(f'Synchronized {sync_catalog()} source definitions; source checks are separate.')
