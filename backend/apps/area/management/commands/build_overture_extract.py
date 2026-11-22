"""Build the local US Overture places extract for a release (redesign B4b); default: the newest."""
from django.core.management.base import BaseCommand, CommandError
from apps.area import overture, overture_extract
from apps.area.http import SourceError


class Command(BaseCommand):
    help = 'Build the US-only Overture places extract (about 5 minutes and 800 MB per release on the droplet).'

    def add_arguments(self, parser):
        parser.add_argument('--release', help='Overture release, e.g. 2026-11-18.0 (default: newest)')

    def handle(self, *args, release=None, **options):
        try:
            release = release or overture.available_releases()[-1]
            m = overture_extract.build(release)
        except SourceError as exc:
            raise CommandError(f'Extract not built: {exc}') from exc
        self.stdout.write(f"{release}: {m['rows']:,} places, {m['bytes'] / 1e6:.0f} MB, sha256 {m['sha256'][:12]}")
