from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from apps.sources.overture_import import import_capture
from apps.sources.health import record_check
from apps.sources.storage import LocalArtifactStore
from apps.sources.models import SourceDefinition

class Command(BaseCommand):
    help = 'Register validated real Overture archives without fabricating a new retrieval time.'
    def add_arguments(self, parser):
        parser.add_argument('--directory',type=Path,required=True)
        parser.add_argument('--store-root',type=Path,required=True)
    def handle(self,*args,**options):
        if not SourceDefinition.objects.filter(pk='SRC-13').exists():
            raise CommandError('Run sync_sources before importing captures.')
        paths=sorted(options['directory'].glob('*/*.manifest.json'))
        if not paths:
            raise CommandError('No capture manifests found.')
        store=LocalArtifactStore(options['store_root'])
        created_count=0
        for path in paths:
            try:
                snapshot,created=import_capture(path,store)
                record_check(source_id=snapshot.source_id,scope=snapshot.scope,
                    run_key="bootstrap:"+snapshot.sha256,succeeded=True,
                    completed_at=snapshot.retrieved_at,snapshot=snapshot)
                created_count+=int(created)
            except (ValueError,KeyError,OSError) as exc:
                raise CommandError(f'Capture rejected: {path.name}: {type(exc).__name__}') from exc
        self.stdout.write(f'Validated {len(paths)} captures; published {created_count}; reused {len(paths)-created_count}.')
