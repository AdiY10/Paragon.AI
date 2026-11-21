"""Compact stored raw Overture captures (R2 item 14) and recompute the release-pair guards."""
from django.conf import settings
from django.core.management.base import BaseCommand
from apps.area import overture_store
from apps.area.models import OvertureCapture
from apps.sources.storage import LocalArtifactStore


class Command(BaseCommand):
    help = 'Compact every raw SRC-13 capture without a compact copy, then refresh release-pair guards.'

    def handle(self, *args, **options):
        store = LocalArtifactStore(settings.SOURCE_ARTIFACT_ROOT)
        done = overture_store.compact_all(store)
        releases = sorted(set(OvertureCapture.objects.values_list('release', flat=True)))
        for prior, latest in zip(releases, releases[1:]):
            row = overture_store.pair(prior, latest, recompute=True)
            self.stdout.write(f'{prior} -> {latest}: {row.cohort_size} pins, broad={row.broad_change}, '
                f'brand drops={row.brand_drops}')
        self.stdout.write(f'Compacted {done} captures.')
