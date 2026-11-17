"""Validate and synchronize the versioned source catalog without inventing health."""
from pathlib import Path
import yaml
from django.conf import settings
from django.db import transaction
from .models import SourceDefinition

FIELDS = {'id','name','provider','purpose','coverage','documentation_url','licence','attribution','cadence','stale_after_days','privacy_note'}


def load_catalog(path=None):
    document = yaml.safe_load(Path(path or settings.BASE_DIR/'config/sources.yaml').read_text())
    if not isinstance(document, dict) or document.get('schema_version') != 1:
        raise ValueError('Unsupported source catalog schema')
    entries = document.get('sources')
    if not isinstance(entries, list) or {e.get('id') for e in entries} != {f'SRC-{i:02}' for i in range(1,17)} or len(entries) != 16:
        raise ValueError('Source catalog must define SRC-01 through SRC-16 exactly once')
    for entry in entries:
        if set(entry) != FIELDS:
            raise ValueError(f'Invalid source catalog fields: {entry.get("id")}')
        for key in FIELDS - {'stale_after_days'}:
            if not isinstance(entry[key], str) or not entry[key].strip():
                raise ValueError(f'Missing catalog field: {key}')
        days = entry['stale_after_days']
        if days is not None and (type(days) is not int or days <= 0):
            raise ValueError('Freshness threshold must be a positive day count or null')
        if not entry['documentation_url'].startswith('https://'):
            raise ValueError('Documentation URL must use HTTPS')
    return document


@transaction.atomic
def sync_catalog(path=None):
    document = load_catalog(path)
    for entry in document['sources']:
        SourceDefinition.objects.update_or_create(id=entry['id'],
            defaults={**{k:v for k,v in entry.items() if k != 'id'},'catalog_version':document['schema_version']})
    return len(document['sources'])
