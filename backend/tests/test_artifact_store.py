from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
import hashlib
import pytest
from apps.sources.storage import LocalArtifactStore, ArtifactIntegrityError


def test_content_addressed_storage_roundtrip_and_dedup(tmp_path):
    store=LocalArtifactStore(tmp_path/'private')
    a=store.put(BytesIO(b'actual response bytes'))
    b=store.put(BytesIO(b'actual response bytes'))
    assert a==b
    assert a.sha256==hashlib.sha256(b'actual response bytes').hexdigest()
    with store.open_verified(a.key) as handle:
        assert handle.read()==b'actual response bytes'
    assert list(store.staging.iterdir())==[]


def test_interrupted_read_never_publishes_partial_artifact(tmp_path):
    class Broken:
        calls=0
        def read(self, size):
            self.calls+=1
            if self.calls==1:return b'partial'
            raise OSError('simulated interrupted upstream')
    store=LocalArtifactStore(tmp_path)
    with pytest.raises(OSError):store.put(Broken())
    assert not list(tmp_path.rglob('sha256'))
    assert not list(store.staging.iterdir())


def test_corrupt_existing_artifact_is_never_silently_reused(tmp_path):
    store=LocalArtifactStore(tmp_path)
    artifact=store.put(BytesIO(b'original'))
    (tmp_path/artifact.key).write_bytes(b'corrupted')
    with pytest.raises(ArtifactIntegrityError):
        with store.open_verified(artifact.key):pass
    with pytest.raises(ArtifactIntegrityError):store.put(BytesIO(b'original'))


@pytest.mark.parametrize('key',['../../secret','sha256/aa/'+'b'*64,'/etc/passwd'])
def test_keys_cannot_escape_private_store(tmp_path,key):
    store=LocalArtifactStore(tmp_path)
    with pytest.raises(ValueError):
        with store.open_verified(key):pass


def test_concurrent_identical_publications_are_complete(tmp_path):
    store=LocalArtifactStore(tmp_path)
    with ThreadPoolExecutor(max_workers=4) as pool:
        artifacts=list(pool.map(lambda _:store.put(BytesIO(b'complete'*10000)),range(8)))
    assert len(set(artifacts))==1
    with store.open_verified(artifacts[0].key) as f:assert f.read()==b'complete'*10000


def test_size_limit_cleans_staging_and_does_not_publish(tmp_path):
    store=LocalArtifactStore(tmp_path)
    with pytest.raises(ValueError,match='size limit'):store.put(BytesIO(b'1234'),max_bytes=3)
    assert not list(store.staging.iterdir())
    artifact=store.put(BytesIO(b''),max_bytes=0)
    assert artifact.size_bytes==0
