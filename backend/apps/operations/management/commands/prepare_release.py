"""Idempotent single-host release preparation, after the private disk is mounted."""
import hashlib
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand,CommandError
from django.db import connection
from apps.sources.storage import LocalArtifactStore

class Command(BaseCommand):
    help='Migrate, optionally import a private workspace, seed missing public records, and bootstrap access.'
    def handle(self,*args,**options):
        # Session lock also covers migrations, which manage their own transactions.
        locked=connection.vendor=='postgresql'
        if locked:
            with connection.cursor() as cursor:cursor.execute('SELECT pg_advisory_lock(%s)',[734992410])
        try:
            store=LocalArtifactStore(settings.SOURCE_ARTIFACT_ROOT)
            # Prove the mounted directory is writable without a confidential payload.
            with NamedTemporaryFile(dir=store.staging):pass
            call_command('migrate',interactive=False,verbosity=0)
            call_command('sync_sources',verbosity=0)
            path=os.environ.get('WORKSPACE_IMPORT_PATH','')
            expected=os.environ.get('WORKSPACE_IMPORT_SHA256','')
            if bool(path)!=bool(expected):raise CommandError('Workspace import requires both private path and SHA-256.')
            if path:
                from apps.locations.workspace_import import import_workspace,MAX_BYTES
                with Path(path).open('rb') as file:raw=file.read(MAX_BYTES+1)
                if hashlib.sha256(raw).hexdigest()!=expected:raise CommandError('Workspace import checksum mismatch.')
                result=import_workspace(raw,apply=True,store=store)
                self.stdout.write(f'Workspace verified: {result.locations} locations; replay={result.reused}.')
            call_command('import_portfolio',verbosity=0)
            call_command('sync_schedules',verbosity=0)
            call_command('bootstrap_access',verbosity=0)
        except (ValueError,OSError) as exc:
            # Do not include imported content or environment values in host logs.
            raise CommandError('Release preparation rejected: '+type(exc).__name__) from None
        finally:
            if locked:
                with connection.cursor() as cursor:cursor.execute('SELECT pg_advisory_unlock(%s)',[734992410])
