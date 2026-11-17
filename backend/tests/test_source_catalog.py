from pathlib import Path
import pytest
from apps.sources.catalog import load_catalog, sync_catalog
from apps.sources.models import SourceDefinition
from backend.tests.test_accounts import member


def test_catalog_covers_all_sources_with_required_freshness():
    entries={entry['id']:entry for entry in load_catalog()['sources']}
    assert len(entries)==16
    assert entries['SRC-14']['stale_after_days']==3
    assert entries['SRC-13']['stale_after_days']==21
    assert entries['SRC-03']['stale_after_days']==45
    assert entries['SRC-02']['stale_after_days'] is None
    assert 'confidential' in entries['SRC-02']['privacy_note']


@pytest.mark.django_db
def test_catalog_sync_is_idempotent_and_preserves_adapter_version():
    assert sync_catalog()==16
    SourceDefinition.objects.filter(pk='SRC-03').update(adapter_version='tested-v1')
    assert sync_catalog()==16
    assert SourceDefinition.objects.count()==16
    assert SourceDefinition.objects.get(pk='SRC-03').adapter_version=='tested-v1'


@pytest.mark.django_db
def test_source_catalog_api_is_private_and_does_not_fabricate_health(client):
    sync_catalog()
    assert client.get('/api/sources/').status_code==403
    user,_=member()
    client.force_login(user)
    data=client.get('/api/sources/').json()
    assert len(data)==16
    assert all('last_checked' not in source and 'status' not in source for source in data)


def test_invalid_catalog_is_rejected_before_writes(tmp_path):
    path=tmp_path/'bad.yaml'
    path.write_text('schema_version: 1\nsources: []\n')
    with pytest.raises(ValueError,match='exactly once'):
        load_catalog(path)
