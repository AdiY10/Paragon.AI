import pytest
from django.core.exceptions import ValidationError
from apps.locations.models import Location,LocationRevision
from apps.locations.service import create_location,update_location,change_pin,confirm_location,LocationConflict
from backend.tests.test_accounts import member

pytestmark=pytest.mark.django_db


def location():return create_location(name='Address under review',address='444 Westport Avenue, Norwalk, CT')


def test_create_unplaced_candidate_preserves_unknowns():
    item=location()
    assert item.status=='candidate' and not item.confirmed
    assert item.gla_sqft is None and item.current_revision.lat is None
    assert item.current_revision.method=='unplaced'


def test_pin_changes_create_history_and_invalidate_analysis_generation():
    user,_=member();item=location();original=item.current_revision
    changed=change_pin(location_id=item.pk,expected_version=1,lat=41.126611,lon=-73.388299,actor=user,confirmed=True)
    assert changed.version==2 and changed.analysis_version==2
    assert changed.current_revision.number==2 and changed.current_revision.confirmed
    original.refresh_from_db();assert original.lat is None
    assert item.revisions.count()==2
    assert item.audit_events.filter(action='pin_changed').exists()


def test_stale_editor_cannot_overwrite_pin_or_attributes():
    user,_=member();item=location()
    update_location(location_id=item.pk,expected_version=1,attributes={'notes':'User-entered note'},actor=user)
    with pytest.raises(LocationConflict):
        change_pin(location_id=item.pk,expected_version=1,lat=41,lon=-73,actor=user)
    assert item.revisions.count()==1


def test_only_analysis_inputs_advance_analysis_version():
    user,_=member();item=location()
    item=update_location(location_id=item.pk,expected_version=1,attributes={'notes':'Review needed'},actor=user)
    assert item.analysis_version==1
    item=update_location(location_id=item.pk,expected_version=2,attributes={'ring_preset':'3/5/10'},actor=user)
    assert item.analysis_version==2


def test_ownership_confirmation_is_explicit_and_attributed():
    user,_=member();item=location()
    confirmed=confirm_location(location_id=item.pk,expected_version=1,actor=user)
    assert confirmed.confirmed and confirmed.confirmed_by==user and confirmed.confirmed_at
    assert confirmed.current_revision.confirmed is False


@pytest.mark.parametrize('lat,lon',[(None,-73),(float('nan'),-73),(91,0),(0,float('inf'))])
def test_invalid_pin_never_creates_location(lat,lon):
    with pytest.raises(ValueError):create_location(name='Invalid',address='Unresolved',lat=lat,lon=lon,pin_method='manual')
    assert not Location.objects.exists()


def test_pin_revisions_cannot_be_rewritten():
    item=location();revision=item.current_revision
    with pytest.raises(ValueError):revision.save()
    with pytest.raises(ValueError):LocationRevision.objects.filter(pk=revision.pk).update(lat=0)


def test_zero_gla_is_not_a_missing_value_substitute():
    user,_=member();item=location()
    with pytest.raises(ValidationError):update_location(location_id=item.pk,expected_version=1,attributes={'gla_sqft':0},actor=user)
    item.refresh_from_db();assert item.gla_sqft is None and item.version==1


def test_revision_from_another_location_cannot_be_current():
    first=location();second=location()
    first.current_revision=second.current_revision
    with pytest.raises(ValidationError,match='different location'):first.full_clean()


@pytest.mark.django_db(transaction=True)
def test_concurrent_pin_editors_cannot_overwrite_each_other():
    from concurrent.futures import ThreadPoolExecutor
    from django.db import connection,connections
    if connection.vendor!='postgresql':pytest.skip('Location edit locking requires PostgreSQL')
    user,_=member();item=location()
    def edit(offset):
        try:
            try:
                change_pin(location_id=item.id,expected_version=1,lat=41+offset/1000,lon=-73,actor=user)
                return True
            except LocationConflict:return False
        finally:connections.close_all()
    with ThreadPoolExecutor(max_workers=2) as pool:result=list(pool.map(edit,[1,2]))
    assert sum(result)==1
    item.refresh_from_db()
    assert item.version==2 and item.revisions.count()==2


def test_address_change_clears_current_pin_and_ownership_but_preserves_history():
    user,_=member();item=location()
    item=change_pin(location_id=item.id,expected_version=1,lat=41.126611,lon=-73.388299,confirmed=True,actor=user)
    item=confirm_location(location_id=item.id,expected_version=2,actor=user)
    old_pin=item.current_revision;old_analysis=item.analysis_version
    changed=update_location(location_id=item.id,expected_version=3,attributes={'address':'445 Main Street, Mount Kisco, NY'},actor=user)
    assert changed.version==4 and changed.analysis_version==old_analysis+1
    assert changed.current_revision.number==3 and changed.current_revision.method=='unplaced'
    assert changed.current_revision.lat is None and not changed.current_revision.confirmed
    assert not changed.confirmed and changed.confirmed_at is None and changed.confirmed_by is None
    old_pin.refresh_from_db();assert old_pin.lat==pytest.approx(41.126611) and old_pin.confirmed
    assert changed.source_context['address_override']['original_address']=='444 Westport Avenue, Norwalk, CT'
    event=item.audit_events.get(action='address_changed')
    assert event.before['confirmed'] and event.after['confirmed'] is False
    assert event.before['revision']==str(old_pin.id)


@pytest.mark.parametrize('field,value',[('city','New municipality'),('state','NY')])
def test_locality_changes_also_require_a_new_pin(field,value):
    user,_=member();item=location()
    changed=update_location(location_id=item.id,expected_version=1,attributes={field:value},actor=user)
    assert changed.current_revision.number==2 and changed.current_revision.method=='unplaced'
    assert changed.analysis_version==2


def test_combined_address_and_ring_change_increments_analysis_once():
    user,_=member();item=location()
    changed=update_location(location_id=item.id,expected_version=1,attributes={'address':'A different saved address','ring_preset':'3/5/10'},actor=user)
    assert changed.analysis_version==2 and changed.current_revision.number==2


def test_unchanged_address_and_notes_keep_pin_and_confirmation():
    user,_=member();item=location();item=confirm_location(location_id=item.id,expected_version=1,actor=user)
    pin=item.current_revision_id
    changed=update_location(location_id=item.id,expected_version=2,attributes={'address':item.address,'notes':'Updated team note'},actor=user)
    assert changed.current_revision_id==pin and changed.analysis_version==1 and changed.confirmed


def test_invalid_address_edit_rolls_back_invalidation_and_revision():
    user,_=member();item=location();pin=item.current_revision_id
    with pytest.raises(ValidationError):update_location(location_id=item.id,expected_version=1,attributes={'address':''},actor=user)
    item.refresh_from_db();assert item.current_revision_id==pin and item.version==1
    assert item.revisions.count()==1 and not item.audit_events.filter(action='address_changed').exists()


def test_repeated_address_changes_retain_original_source_address():
    user,_=member();item=location();original=item.address
    changed=update_location(location_id=item.id,expected_version=1,attributes={'address':'First team correction'},actor=user)
    final=update_location(location_id=item.id,expected_version=2,attributes={'address':'Second team correction'},actor=user)
    assert final.source_context['address_override']['original_address']==original
    assert final.revisions.count()==3
