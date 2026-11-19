from dataclasses import asdict
import json
from pathlib import Path
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand,CommandError
from apps.locations.workspace_import import import_workspace,MAX_BYTES

class Command(BaseCommand):
    help='Validate a complete single-workspace export; apply only with --apply, never overwrite destination edits.'
    def add_arguments(self,parser):
        parser.add_argument('path',type=Path)
        parser.add_argument('--apply',action='store_true')
    def handle(self,*args,**options):
        try:
            with options['path'].open('rb') as file:raw=file.read(MAX_BYTES+1)
            result=import_workspace(raw,apply=options['apply'])
        except (ValueError,KeyError,TypeError,ValidationError,OSError) as exc:
            raise CommandError('Workspace import rejected: '+(str(exc) if isinstance(exc,ValueError) else type(exc).__name__)) from None
        self.stdout.write(json.dumps(asdict(result)))
