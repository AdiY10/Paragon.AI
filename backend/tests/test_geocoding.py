from datetime import timedelta
from pathlib import Path
from unittest.mock import Mock
import hashlib
import pytest
from django.utils import timezone
from apps.locations.census import parse_census,CensusCapture,GeocoderError
from apps.locations.geocoding import request_lookup,accept_lookup,lookup_payload,lookup_address
from apps.locations.models import GeocodeLookup
from apps.locations.service import create_location,update_location,change_pin,LocationConflict
from apps.sources.catalog import sync_catalog
from apps.sources.models import SourceSnapshot,SourceCheck
from apps.sources.storage import LocalArtifactStore
from backend.tests.test_accounts import member

pytestmark=pytest.mark.django_db


def capture(name='norwalk',when=None):
    raw=Path(f'tests/fixtures/real/census_geocoder/{name}.json').read_bytes()
    return CensusCapture(parse_census(raw),raw,hashlib.sha256(raw).hexdigest(),when or timezone.now())


@pytest.fixture
def setup_lookup(tmp_path):
    sync_catalog();user,_=member()
    item=create_location(name='Review address',address='444 Westport Avenue, Norwalk, CT 06851')
    store=LocalArtifactStore(tmp_path/'private-store');fetcher=Mock(return_value=capture())
    return user,item,store,fetcher


def preview(setup):
    user,item,store,fetcher=setup
    return request_lookup(location_id=item.id,expected_version=item.version,actor=user,store=store,fetcher=fetcher)


def test_lookup_persists_private_evidence_without_changing_pin(setup_lookup):
    user,item,store,fetcher=setup_lookup
    lookup=preview(setup_lookup);item.refresh_from_db()
    assert item.version==1 and item.current_revision.method=='unplaced'
    assert lookup.status=='matched' and not item.confirmed
    assert SourceSnapshot.objects.count()==1 and SourceCheck.objects.count()==1
    snapshot=lookup.snapshot
    assert snapshot.source_url.endswith('/onelineaddress') and '?' not in snapshot.source_url
    assert 'Westport' not in snapshot.scope and 'Westport' not in str(snapshot.context)
    with store.open_verified(snapshot.artifact_key) as file:assert file.read()==fetcher.return_value.raw
    assert lookup_payload(lookup)['last_checked_at']==lookup.checked_at


def test_cached_replay_does_not_claim_new_source_check(setup_lookup):
    first=preview(setup_lookup);second=preview(setup_lookup)
    assert first.pk==second.pk and second.checked_at==first.checked_at
    assert SourceCheck.objects.count()==1 and setup_lookup[3].call_count==1


def test_shared_location_cache_retains_per_user_preview_privacy(setup_lookup):
    user,item,store,fetcher=setup_lookup;first=preview(setup_lookup)
    colleague,_=member('colleague@example.org')
    second=request_lookup(location_id=item.id,expected_version=1,actor=colleague,store=store,fetcher=fetcher)
    assert second.id!=first.id and second.snapshot_id==first.snapshot_id
    assert second.checked_at==first.checked_at and fetcher.call_count==1
    with pytest.raises(GeocodeLookup.DoesNotExist):
        accept_lookup(location_id=item.id,lookup_id=first.id,expected_version=1,candidate_index=0,actor=colleague)


def test_accept_uses_stored_suggestion_and_remains_unverified(setup_lookup):
    user,item,_,_=setup_lookup;lookup=preview(setup_lookup)
    changed=accept_lookup(location_id=item.id,lookup_id=lookup.id,expected_version=1,candidate_index=0,actor=user)
    pin=changed.current_revision
    assert pin.method=='census_interpolated' and pin.lat==pytest.approx(41.12661107292)
    assert pin.matched_address and not pin.confirmed and not changed.confirmed
    assert pin.context['geographies']['county']['geoid']=='09190'
    assert pin.context['geographies']['block']['geoid']=='090010435001001'
    assert pin.context['snapshot_id']==str(lookup.snapshot_id)
    assert changed.analysis_version==2 and changed.version==2
    repeated=accept_lookup(location_id=item.id,lookup_id=lookup.id,expected_version=1,candidate_index=0,actor=user)
    assert repeated.current_revision_id==pin.id and item.revisions.count()==2


def test_ambiguous_choice_and_no_match_are_explicit(setup_lookup):
    user,item,store,fetcher=setup_lookup;fetcher.return_value=capture('mount_kisco')
    lookup=preview(setup_lookup);assert lookup.status=='ambiguous' and len(lookup.candidates)==2
    changed=accept_lookup(location_id=item.id,lookup_id=lookup.id,expected_version=1,candidate_index=1,actor=user)
    assert changed.current_revision.lat==lookup.candidates[1]['lat']
    other=create_location(name='Kingston public address',address='1200 Ulster Avenue, Kingston, NY')
    fetcher.return_value=capture('kingston')
    missing=request_lookup(location_id=other.id,expected_version=1,actor=user,store=store,fetcher=fetcher)
    assert missing.status=='no_match'
    with pytest.raises(ValueError):accept_lookup(location_id=other.id,lookup_id=missing.id,expected_version=1,candidate_index=0,actor=user)
    other.refresh_from_db();assert other.current_revision.method=='unplaced'


def test_new_pin_during_provider_request_cannot_be_overwritten(setup_lookup):
    user,item,store,fetcher=setup_lookup
    def edited(address):
        change_pin(location_id=item.id,expected_version=1,lat=41,lon=-73,actor=user,confirmed=True)
        return capture()
    fetcher.side_effect=edited
    with pytest.raises(LocationConflict):preview(setup_lookup)
    item.refresh_from_db();assert item.current_revision.confirmed and item.current_revision.method=='manual'
    assert SourceSnapshot.objects.count()==1 and not GeocodeLookup.objects.exists()


def test_edits_after_preview_and_changed_address_reject_acceptance(setup_lookup):
    user,item,_,_=setup_lookup;lookup=preview(setup_lookup)
    update_location(location_id=item.id,expected_version=1,attributes={'address':'445 Main Street, Mount Kisco, NY'},actor=user)
    with pytest.raises(LocationConflict):accept_lookup(location_id=item.id,lookup_id=lookup.id,expected_version=1,candidate_index=0,actor=user)


def test_expiry_refetch_keeps_old_snapshot_time_but_real_new_check(setup_lookup):
    user,item,store,fetcher=setup_lookup
    fetcher.return_value=capture(when=timezone.now()-timedelta(days=31))
    old=preview(setup_lookup)
    with pytest.raises(LocationConflict):accept_lookup(location_id=item.id,lookup_id=old.id,expected_version=1,candidate_index=0,actor=user)
    fetcher.return_value=capture()
    new=preview(setup_lookup)
    assert new.pk!=old.pk and new.snapshot_id==old.snapshot_id
    assert new.snapshot.retrieved_at==old.snapshot.retrieved_at and new.checked_at>old.checked_at
    assert new.expires_at>timezone.now() and SourceCheck.objects.count()==2


def test_failure_retains_pin_and_records_only_sanitized_failure(setup_lookup):
    user,item,_,fetcher=setup_lookup;fetcher.side_effect=GeocoderError('TIMEOUT')
    with pytest.raises(GeocoderError,match='TIMEOUT'):preview(setup_lookup)
    item.refresh_from_db();assert item.version==1 and item.current_revision.method=='unplaced'
    assert not GeocodeLookup.objects.exists() and not SourceSnapshot.objects.exists()
    assert SourceCheck.objects.get().error_code=='TIMEOUT'


def test_stale_request_does_not_contact_provider(setup_lookup):
    user,item,store,fetcher=setup_lookup
    update_location(location_id=item.id,expected_version=1,attributes={'notes':'Newer note'},actor=user)
    with pytest.raises(LocationConflict):preview(setup_lookup)
    fetcher.assert_not_called()


def test_missing_catalog_does_not_contact_provider(tmp_path):
    user,_=member();item=create_location(name='Address',address='444 Westport Avenue, Norwalk, CT')
    fetcher=Mock()
    with pytest.raises(GeocoderError,match='NOT_CONFIGURED'):
        request_lookup(location_id=item.id,expected_version=1,actor=user,fetcher=fetcher,store=LocalArtifactStore(tmp_path))
    fetcher.assert_not_called()


def test_address_assembly_uses_tokens_for_city_and_state():
    item=create_location(name='Address',address='123 Market Street',city='Stuttgart',state='AR')
    assert lookup_address(item)=='123 Market Street, Stuttgart, AR'


def test_private_api_returns_preview_and_requires_explicit_acceptance(client,settings,tmp_path,monkeypatch):
    sync_catalog();user,_=member();client.force_login(user);settings.SOURCE_ARTIFACT_ROOT=tmp_path/'api-artifacts'
    item=create_location(name='Reference address',address='444 Westport Avenue, Norwalk, CT 06851')
    monkeypatch.setattr('apps.locations.geocoding.fetch_census',Mock(return_value=capture()))
    path=f'/api/locations/{item.id}/geocode/'
    response=client.post(path,{'expected_version':1},content_type='application/json')
    assert response.status_code==200
    body=response.json();assert body['status']=='matched' and body['source']['sha256']
    item.refresh_from_db();assert item.current_revision.lat is None
    accepted=client.post(path+body['id']+'/accept/',{'expected_version':1,'candidate_index':0},content_type='application/json')
    assert accepted.status_code==200 and accepted.json()['current_revision']['method']=='census_interpolated'
    assert not accepted.json()['current_revision']['confirmed']
    assert client.post(path+body['id']+'/accept/',{'expected_version':1,'candidate_index':0,'lat':0},content_type='application/json').status_code==400


def test_api_rejects_anonymous_and_cross_record_or_other_users_lookup(client,setup_lookup):
    user,item,_,_=setup_lookup;lookup=preview(setup_lookup);path=f'/api/locations/{item.id}/geocode/'
    assert client.post(path,{'expected_version':1}).status_code==403
    other,_=member('other@example.org');client.force_login(other)
    assert client.post(path+str(lookup.id)+'/accept/',{'expected_version':1,'candidate_index':0},content_type='application/json').status_code==404
    client.force_login(user);second=create_location(name='Other record',address='Other saved address')
    assert client.post(f'/api/locations/{second.id}/geocode/{lookup.id}/accept/',{'expected_version':1,'candidate_index':0},content_type='application/json').status_code==404


def test_lookup_failure_api_exposes_only_sanitized_code(client,setup_lookup,monkeypatch):
    user,item,_,_=setup_lookup;client.force_login(user)
    monkeypatch.setattr('apps.locations.geocoding.fetch_census',Mock(side_effect=GeocoderError('TIMEOUT')))
    response=client.post(f'/api/locations/{item.id}/geocode/',{'expected_version':1},content_type='application/json')
    assert response.status_code==503 and response.json()['code']=='TIMEOUT'
    assert b'Westport' not in response.content and b'geocoding.geo' not in response.content


@pytest.mark.django_db(transaction=True)
def test_concurrent_accepts_create_one_revision(setup_lookup):
    from concurrent.futures import ThreadPoolExecutor
    from django.db import connection,connections
    if connection.vendor!='postgresql':pytest.skip('Geocode acceptance locks require PostgreSQL')
    user,item,_,_=setup_lookup;lookup=preview(setup_lookup)
    def accept(_):
        try:return accept_lookup(location_id=item.id,lookup_id=lookup.id,expected_version=1,candidate_index=0,actor=user).current_revision_id
        finally:connections.close_all()
    with ThreadPoolExecutor(max_workers=2) as pool:ids=list(pool.map(accept,[1,2]))
    assert ids[0]==ids[1] and item.revisions.count()==2
