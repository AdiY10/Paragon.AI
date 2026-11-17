from copy import deepcopy
import hashlib
import json
from pathlib import Path
import pytest
from apps.sources.catalog import sync_catalog
from apps.sources.models import SourceSnapshot
from apps.sources.overture_import import import_capture
from apps.sources.storage import LocalArtifactStore

pytestmark=pytest.mark.django_db


def archived_pair(tmp_path):
    fixture=Path('tests/fixtures/real/overture')
    manifest=deepcopy(json.loads((fixture/'manifest.json').read_text())['extracts'][1])
    record=json.loads((fixture/'regal-status-change.json').read_text())['after']
    payload=json.dumps([record]).encode()
    manifest['record_count']=1
    manifest['sha256']=hashlib.sha256(payload).hexdigest()
    root=tmp_path/'archive'/manifest['release'];root.mkdir(parents=True)
    path=root/'P20.manifest.json';path.write_text(json.dumps(manifest))
    path.with_name('P20.json').write_bytes(payload)
    return path,manifest


def test_import_preserves_real_record_attribution_pin_and_retrieval(tmp_path):
    sync_catalog()
    path,manifest=archived_pair(tmp_path)
    store=LocalArtifactStore(tmp_path/'store')
    snapshot,created=import_capture(path,store)
    assert created
    assert snapshot.record_count==1
    assert snapshot.retrieved_at.isoformat()==manifest['retrieved_at']
    assert snapshot.context['coordinates']==manifest['coordinates']
    assert snapshot.context['pin_status']=='unconfirmed_seed_reference'
    with store.open_verified(snapshot.artifact_key) as handle:
        record=json.load(handle)[0]
        assert record['name']=='Regal Cinemas Hudson Valley Mall 12'
        assert record['sources'][0]['license']=='Apache-2.0'
    assert not import_capture(path,store)[1]


def test_corrupt_capture_is_rejected_without_snapshot(tmp_path):
    sync_catalog()
    path,_=archived_pair(tmp_path)
    path.with_name('P20.json').write_bytes(b'corrupted')
    with pytest.raises(ValueError,match='checksum'):
        import_capture(path,LocalArtifactStore(tmp_path/'store'))
    assert not SourceSnapshot.objects.exists()


def test_missing_attribution_column_fails_closed(tmp_path):
    sync_catalog()
    path,manifest=archived_pair(tmp_path)
    manifest['schema'].remove('sources')
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError,match='unsupported schema'):
        import_capture(path,LocalArtifactStore(tmp_path/'store'))
    assert not SourceSnapshot.objects.exists()


def test_capture_with_reassigned_pin_is_rejected(tmp_path):
    sync_catalog()
    path,manifest=archived_pair(tmp_path)
    manifest['coordinates']={'lat':0,'lon':0}
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError,match='outside the capture radius'):
        import_capture(path,LocalArtifactStore(tmp_path/'store'))
    assert not SourceSnapshot.objects.exists()
