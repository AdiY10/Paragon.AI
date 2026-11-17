from datetime import timedelta
from io import BytesIO
import pytest
from django.utils import timezone
from apps.sources.catalog import sync_catalog
from apps.sources.models import SourceSnapshot
from apps.sources.snapshots import publish_snapshot, ValidationReport
from apps.sources.storage import LocalArtifactStore

pytestmark=pytest.mark.django_db


def publish(tmp_path,**overrides):
    values=dict(source_id='SRC-13',scope='P20:reference-pin',release='2026-10-21.0',
        data_period='Overture 2026-10-21.0',source_url='https://public.example.org/release?key=secret&address=private',
        adapter_version='places-v1',stream=BytesIO(b'{"real":"test-only response"}'),
        store=LocalArtifactStore(tmp_path),validation=ValidationReport(True,True,{'fields':['real']},1))
    values.update(overrides)
    return publish_snapshot(**values)


def test_snapshot_publication_is_idempotent_and_preserves_first_retrieval(tmp_path):
    sync_catalog()
    first,created=publish(tmp_path,retrieved_at=timezone.now()-timedelta(days=1))
    assert created
    second,created=publish(tmp_path)
    assert not created
    assert first.id==second.id
    assert second.retrieved_at==first.retrieved_at
    assert '?' not in first.source_url
    assert SourceSnapshot.objects.count()==1


def test_invalid_or_incomplete_source_never_publishes(tmp_path):
    sync_catalog()
    with pytest.raises(ValueError,match='incomplete'):
        publish(tmp_path,validation=ValidationReport(True,False,{'fields':['real']},1))
    assert SourceSnapshot.objects.count()==0
    assert not list(tmp_path.rglob('sha256'))


def test_failed_artifact_write_never_publishes_database_row(tmp_path):
    sync_catalog()
    class FailedStore:
        def put(self,*args,**kwargs):raise OSError('storage unavailable')
    with pytest.raises(OSError):publish(tmp_path,store=FailedStore())
    assert not SourceSnapshot.objects.exists()


def test_published_snapshots_cannot_be_edited_or_deleted(tmp_path):
    sync_catalog()
    snapshot,_=publish(tmp_path)
    snapshot.data_period='changed'
    with pytest.raises(ValueError,match='immutable'):snapshot.save()
    with pytest.raises(ValueError,match='immutable'):SourceSnapshot.objects.filter(pk=snapshot.pk).update(data_period='changed')
    with pytest.raises(ValueError):snapshot.delete()
    with pytest.raises(ValueError):SourceSnapshot.objects.all().delete()


def test_same_content_with_conflicting_schema_fails(tmp_path):
    sync_catalog()
    publish(tmp_path)
    with pytest.raises(ValueError,match='conflicting provenance'):
        publish(tmp_path,validation=ValidationReport(True,True,{'fields':['different']},1))
    assert SourceSnapshot.objects.count()==1


def test_changed_source_revision_retains_history(tmp_path):
    sync_catalog()
    first,_=publish(tmp_path)
    second,created=publish(tmp_path,stream=BytesIO(b'{"real":"revised"}'))
    assert created and first.id!=second.id
    assert SourceSnapshot.objects.count()==2


@pytest.mark.parametrize('url',['http://example.org/source','https://secret:password@example.org/source'])
def test_source_link_rejects_insecure_or_embedded_credentials(tmp_path,url):
    sync_catalog()
    with pytest.raises(ValueError,match='without credentials'):publish(tmp_path,source_url=url)
