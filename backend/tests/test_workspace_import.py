from copy import deepcopy
from datetime import timedelta
import hashlib
import json
from pathlib import Path
import uuid
import pytest
from django.utils import timezone
from apps.locations.models import Location,LocationRevision,WorkspaceImport,ImportedSiteAudit
from apps.locations.seeding import import_public_portfolio
from apps.locations.service import update_location
from apps.locations.workspace_import import import_workspace
from apps.sources.catalog import sync_catalog
from apps.sources.storage import LocalArtifactStore
from backend.tests.test_accounts import member

pytestmark=pytest.mark.django_db

@pytest.fixture
def bundle(tmp_path):
    sync_catalog();import_public_portfolio()
    data=json.loads(Path('sites/temporary/data/bootstrap.json').read_text())
    data.update(schema_version=3,workspace_id='isolated-test-workspace',source_project_id='isolated-test-site',revisions=[],audits=[],geocode_lookups=[],source_checks=[])
    return data,LocalArtifactStore(tmp_path/'private-evidence')


def encoded(data):return json.dumps(data).encode()


def test_real_public_snapshot_dry_run_and_apply_are_complete_and_idempotent(bundle):
    data,store=bundle;raw=encoded(data)
    result=import_workspace(raw,store=store)
    assert not result.applied and result.locations==36 and not WorkspaceImport.objects.exists()
    assert not list(store.root.glob('sha256/*/*'))
    applied=import_workspace(raw,apply=True,store=store)
    assert applied.applied and applied.locations==36 and Location.objects.count()==36
    assert not Location.objects.filter(confirmed=True).exists()
    receipt=WorkspaceImport.objects.get();assert receipt.sha256==hashlib.sha256(raw).hexdigest()
    with store.open_verified(receipt.artifact_key) as file:assert file.read()==raw
    assert import_workspace(raw,apply=True,store=store).reused
    assert WorkspaceImport.objects.count()==1


def edited_bundle(bundle):
    data,store=bundle;row=next(row for row in data['locations'] if row['seed_id']=='P03')
    row['notes']='Private team note in isolated test';row['version']=2;row['analysis_version']=2
    old=deepcopy(row['current_revision']);new={**old,'id':str(uuid.uuid4()),'number':2,'method':'manual','lat':41.1266,'lon':-73.3882,'confirmed':True,'context':{'nature':'User-provided'},'created_at':(timezone.now()-timedelta(minutes=5)).isoformat()}
    row['current_revision']=new
    data['revisions']=[{**old,'location_id':row['id']},{**new,'location_id':row['id']}]
    event={'id':str(uuid.uuid4()),'location_id':row['id'],'action':'pin_changed','actor':'source-test@example.invalid','created_at':new['created_at'],'before':{'revision':old['id']},'after':{'revision':new['id']}}
    data['audits']=[event]
    return data,store,row,event


def test_notes_pins_dates_actor_metadata_and_history_survive_without_auth_grants(bundle,client):
    data,store,row,event=edited_bundle(bundle)
    import_workspace(encoded(data),apply=True,store=store)
    item=Location.objects.get(seed_id='P03');pin=item.current_revision
    assert item.notes==row['notes'] and pin.confirmed and pin.method=='manual' and not item.confirmed
    assert pin.created_at.isoformat()==event['created_at'] and pin.context['migration']['original_revision_id']==row['current_revision']['id']
    assert item.revisions.count()==2 and ImportedSiteAudit.objects.get().actor_email==event['actor']
    user,_=member();client.force_login(user)
    history=client.get(f'/api/locations/{item.id}/history/').json()['results']
    imported=next(entry for entry in history if entry['action']=='pin_changed')
    assert imported['actor']==event['actor'] and imported['after']['revision']==str(pin.id)
    assert not user.email==event['actor']


def test_exact_replay_preserves_destination_edits(bundle):
    data,store=bundle;raw=encoded(data);import_workspace(raw,apply=True,store=store)
    user,_=member();item=Location.objects.get(seed_id='P03')
    update_location(location_id=item.id,expected_version=item.version,attributes={'notes':'New destination note'},actor=user)
    assert import_workspace(raw,apply=True,store=store).reused
    item.refresh_from_db();assert item.notes=='New destination note'


def test_changed_destination_is_not_overwritten_and_transaction_rolls_back(bundle):
    data,store=bundle;user,_=member();item=Location.objects.get(seed_id='P36')
    update_location(location_id=item.id,expected_version=1,attributes={'notes':'Retain destination data'},actor=user)
    with pytest.raises(ValueError,match='Destination has edits'):import_workspace(encoded(data),apply=True,store=store)
    assert not WorkspaceImport.objects.exists()
    assert Location.objects.get(seed_id='P01').version==1


@pytest.mark.parametrize('mutate',[
    lambda d:d['locations'].pop(),
    lambda d:d['locations'][0].update(gla_sqft=-1),
    lambda d:d['locations'][0]['current_revision'].update(lat=float('nan')),
    lambda d:d.update(schema_version=99),
    lambda d:d['locations'][0].update(source_url='javascript:alert(1)'),
])
def test_invalid_exports_reject_without_any_data_or_artifact_writes(bundle,mutate):
    data,store=bundle;mutate(data)
    with pytest.raises(ValueError):import_workspace(encoded(data),apply=True,store=store)
    assert not WorkspaceImport.objects.exists() and not list(store.root.glob('sha256/*/*'))
    assert Location.objects.get(seed_id='P03').version==1


def test_history_without_location_links_is_rejected_instead_of_discarded(bundle):
    data,store,_,_=edited_bundle(bundle);data['audits'][0].pop('location_id')
    with pytest.raises(ValueError,match='relationships'):import_workspace(encoded(data),apply=True,store=store)
    assert not ImportedSiteAudit.objects.exists()


def test_missing_pin_revision_is_not_silently_reconstructed(bundle):
    data,store,row,_=edited_bundle(bundle);data['revisions']=[]
    with pytest.raises(ValueError,match='history is incomplete'):import_workspace(encoded(data),apply=True,store=store)
    assert not WorkspaceImport.objects.exists()


def test_receipts_and_imported_history_are_immutable(bundle):
    data,store,_,_=edited_bundle(bundle);import_workspace(encoded(data),apply=True,store=store)
    receipt=WorkspaceImport.objects.get();event=ImportedSiteAudit.objects.get()
    with pytest.raises(ValueError):receipt.save()
    with pytest.raises(ValueError):event.delete()


def test_census_original_bytes_and_source_dates_survive(bundle):
    from apps.locations.census import parse_census
    from apps.sources.models import SourceSnapshot,SourceCheck
    data,store=bundle;row=data['locations'][0]
    raw=Path('tests/fixtures/real/census_geocoder/norwalk.json').read_bytes();parsed=parse_census(raw)
    retrieved=(timezone.now()-timedelta(days=2)).isoformat();source_id=str(uuid.uuid4())
    lookup={'id':str(uuid.uuid4()),'location_id':row['id'],'raw_response':raw.decode(),'status':parsed.status,
        'candidates':list(parsed.candidates),'source':{'sha256':hashlib.sha256(raw).hexdigest(),'snapshot_id':source_id},'retrieved_at':retrieved}
    data['geocode_lookups']=[lookup]
    data['source_checks']=[{'id':str(uuid.uuid4()),'location_id':row['id'],'succeeded':True,'completed_at':retrieved,'snapshot_id':source_id}]
    import_workspace(encoded(data),apply=True,store=store)
    snapshot=SourceSnapshot.objects.get(sha256=hashlib.sha256(raw).hexdigest())
    assert snapshot.retrieved_at.isoformat()==retrieved
    with store.open_verified(snapshot.artifact_key) as file:assert file.read()==raw
    assert SourceCheck.objects.get(snapshot=snapshot).completed_at==snapshot.retrieved_at


def test_duplicate_seed_identity_is_rejected_before_writing(bundle):
    data,store=bundle;extra=deepcopy(data['locations'][0]);extra['id']=str(uuid.uuid4());data['locations'].append(extra)
    with pytest.raises(ValueError,match='Duplicate source seed'):import_workspace(encoded(data),apply=True,store=store)
    assert not WorkspaceImport.objects.exists()
