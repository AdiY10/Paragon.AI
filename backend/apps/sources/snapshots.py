"""Publish validated source snapshots only after artifact persistence succeeds."""
from dataclasses import dataclass
from datetime import datetime
from typing import BinaryIO
from urllib.parse import urlsplit, urlunsplit
from django.db import transaction
from django.utils import timezone
from .models import SourceDefinition, SourceSnapshot
from .storage import ArtifactStore


@dataclass(frozen=True)
class ValidationReport:
    passed: bool
    complete: bool
    schema: dict
    record_count: int
    errors: tuple[str, ...] = ()

    def require_publishable(self):
        if self.passed is not True or self.complete is not True or self.errors:
            raise ValueError('Failed or incomplete source batches cannot be published')
        if not self.schema or not isinstance(self.schema, dict):
            raise ValueError('A verified source schema is required')
        if type(self.record_count) is not int or self.record_count < 0:
            raise ValueError('A nonnegative verified record count is required')


def public_source_url(url):
    parsed = urlsplit(url)
    if parsed.scheme not in ('https','s3') or not parsed.netloc or parsed.username or parsed.password:
        raise ValueError('Source URL must identify a secure source without credentials')
    # Keys, confidential address queries, or fragments do not belong in source links.
    return urlunsplit((parsed.scheme,parsed.netloc,parsed.path,'',''))


def publish_snapshot(*, source_id: str, scope: str, release: str, data_period: str,
        source_url: str, adapter_version: str, stream: BinaryIO, store: ArtifactStore,
        validation: ValidationReport, retrieved_at: datetime | None = None,
        max_bytes=256*1024*1024):
    validation.require_publishable()
    for field, value, max_length in [('scope',scope,160),('release',release,96),
            ('data_period',data_period,160),('adapter_version',adapter_version,64)]:
        if not isinstance(value,str) or not value.strip() or len(value)>max_length:
            raise ValueError(f'Invalid snapshot {field}')
    if adapter_version == 'unimplemented':
        raise ValueError('Snapshot adapter must have an implementation version')
    source_url = public_source_url(source_url)
    retrieved_at = retrieved_at or timezone.now()
    if timezone.is_naive(retrieved_at) or retrieved_at > timezone.now():
        raise ValueError('Retrieval time must be timezone-aware and not in the future')
    source = SourceDefinition.objects.get(pk=source_id)
    artifact = store.put(stream,max_bytes=max_bytes)
    # An object persisted before a failed DB transaction may become an orphan, but
    # no published row can point to a partial or nonexistent upload.
    with transaction.atomic():
        snapshot, created = SourceSnapshot.objects.get_or_create(
            source=source,scope=scope,release=release,sha256=artifact.sha256,
            adapter_version=adapter_version,
            defaults={'data_period':data_period,'source_url':source_url,
                'retrieved_at':retrieved_at,'source_schema':validation.schema,
                'record_count':validation.record_count,'artifact_key':artifact.key,
                'size_bytes':artifact.size_bytes})
        if not created and (snapshot.source_schema != validation.schema or
                snapshot.record_count != validation.record_count or
                snapshot.data_period != data_period or snapshot.source_url != source_url):
            raise ValueError('Identical source content was submitted with conflicting provenance')
    return snapshot, created
