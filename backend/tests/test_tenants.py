import uuid
import pytest
from django.core.exceptions import ValidationError
from apps.locations.models import Tenant,TenantAudit
from apps.locations.service import create_location,update_location,LocationConflict
from apps.locations.tenants import create_tenant,edit_tenant,confirm_tenant,name_key
from backend.tests.test_accounts import member

pytestmark=pytest.mark.django_db

@pytest.fixture
def roster():
    user,_=member();location=create_location(name='User-reviewed shopping center',address='444 Westport Avenue, Norwalk, CT',status='owned')
    return user,location


def add(roster,name='Staples',key=None,**kwargs):
    user,item=roster
    return create_tenant(location_id=item.id,name=name,request_key=key or uuid.uuid4(),actor=user,**kwargs)


def test_create_is_unconfirmed_with_unknown_anchor_and_attributed_history(roster):
    tenant,created=add(roster);user,item=roster
    assert created and not tenant.confirmed and tenant.is_anchor is None
    assert tenant.origin=='user' and not tenant.source_url
    assert tenant.history.get().actor==user and tenant.history.get().action=='created'
    item.refresh_from_db();assert item.version==2 and item.analysis_version==1  # R2.10: tenants leave the analysis valid


def test_request_replay_does_not_duplicate_or_overwrite_later_edits(roster):
    key=uuid.uuid4();tenant,_=add(roster,key=key)
    edit_tenant(location_id=roster[1].id,tenant_id=tenant.id,expected_version=1,attributes={'notes':'Team-reviewed note'},actor=roster[0])
    replay,created=add(roster,key=key)
    assert replay.id==tenant.id and not created and replay.notes=='Team-reviewed note'
    assert Tenant.objects.count()==1 and TenantAudit.objects.count()==2
    with pytest.raises(LocationConflict):add(roster,name='GNC',key=key)


def test_cautious_name_normalization_does_not_merge_brands_and_parents(roster):
    add(roster,name='  LOWE’S  ')
    with pytest.raises(LocationConflict):add(roster,name="Lowe's")
    assert name_key('TJ Maxx')!=name_key('The TJX Companies, Inc.')
    assert name_key('AT&T')!=name_key('ATT')
    assert add(roster,name='The TJX Companies, Inc.')[1]


def test_confirm_and_rename_require_separate_review(roster):
    tenant,_=add(roster);user,item=roster
    confirmed=confirm_tenant(location_id=item.id,tenant_id=tenant.id,expected_version=1,actor=user)
    assert confirmed.confirmed and confirmed.confirmed_by==user and confirmed.confirmed_at
    renamed=edit_tenant(location_id=item.id,tenant_id=tenant.id,expected_version=2,attributes={'name':'GNC'},actor=user)
    assert not renamed.confirmed and renamed.confirmed_at is None
    assert renamed.source_context['name_override']['original_name']=='Staples'
    with pytest.raises(LocationConflict):confirm_tenant(location_id=item.id,tenant_id=tenant.id,expected_version=2,actor=user)


def test_archive_retains_history_and_restore_does_not_restore_confirmation(roster):
    tenant,_=add(roster);user,item=roster
    confirm_tenant(location_id=item.id,tenant_id=tenant.id,expected_version=1,actor=user)
    archived=edit_tenant(location_id=item.id,tenant_id=tenant.id,expected_version=2,attributes={'archived':True},actor=user)
    assert archived.archived and not archived.confirmed
    with pytest.raises(ValueError):confirm_tenant(location_id=item.id,tenant_id=tenant.id,expected_version=3,actor=user)
    restored=edit_tenant(location_id=item.id,tenant_id=tenant.id,expected_version=3,attributes={'archived':False},actor=user)
    assert not restored.archived and not restored.confirmed and restored.history.count()==4


def test_restore_cannot_collide_with_another_active_record(roster):
    tenant,_=add(roster);user,item=roster
    edit_tenant(location_id=item.id,tenant_id=tenant.id,expected_version=1,attributes={'archived':True},actor=user)
    add(roster)
    with pytest.raises(LocationConflict):edit_tenant(location_id=item.id,tenant_id=tenant.id,expected_version=2,attributes={'archived':False},actor=user)
    tenant.refresh_from_db();assert tenant.archived and tenant.version==2


def test_unsupported_source_or_mapping_fields_never_mutate_tenant(roster):
    tenant,_=add(roster)
    for fields in [{'origin':'public_seed'},{'confirmed':True},{'cik':'0000084129'},{'is_anchor':'yes'},{'notes':'x'*5001}]:
        with pytest.raises(ValueError):edit_tenant(location_id=roster[1].id,tenant_id=tenant.id,expected_version=1,attributes=fields,actor=roster[0])
    tenant.refresh_from_db();assert tenant.version==1 and not tenant.confirmed


def test_only_owned_properties_allow_roster_mutations(roster):
    user,item=roster
    update_location(location_id=item.id,expected_version=1,attributes={'status':'candidate'},actor=user)
    with pytest.raises(ValueError,match='owned'):add(roster)
    assert not Tenant.objects.exists()


def test_address_change_retires_existing_tenants_and_invalid_edits_roll_back(roster):
    tenant,_=add(roster);user,item=roster
    confirm_tenant(location_id=item.id,tenant_id=tenant.id,expected_version=1,actor=user)
    item.refresh_from_db();version=item.version
    with pytest.raises(ValidationError):update_location(location_id=item.id,expected_version=version,attributes={'address':''},actor=user)
    tenant.refresh_from_db();assert not tenant.archived and tenant.confirmed
    update_location(location_id=item.id,expected_version=version,attributes={'address':'A different saved address'},actor=user)
    tenant.refresh_from_db();assert tenant.archived and not tenant.confirmed and tenant.version==3
    assert tenant.history.filter(action='address_archived').count()==1


def test_tenant_audit_cannot_be_rewritten_or_deleted(roster):
    tenant,_=add(roster);entry=tenant.history.get()
    with pytest.raises(ValueError):entry.save()
    with pytest.raises(ValueError):TenantAudit.objects.filter(pk=entry.id).update(action='changed')
    with pytest.raises(ValueError):entry.delete()


@pytest.mark.django_db(transaction=True)
def test_concurrent_replayed_creation_is_one_record(roster):
    from concurrent.futures import ThreadPoolExecutor
    from django.db import connection,connections
    if connection.vendor!='postgresql':pytest.skip('Tenant mutation locks require PostgreSQL')
    key=uuid.uuid4()
    def create(_):
        try:return add(roster,key=key)[1]
        finally:connections.close_all()
    with ThreadPoolExecutor(max_workers=2) as pool:created=list(pool.map(create,[1,2]))
    assert sorted(created)==[False,True]
    assert Tenant.objects.count()==1 and TenantAudit.objects.count()==1
