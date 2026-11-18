from pathlib import Path
import pytest
from apps.sources.catalog import sync_catalog
from apps.locations.models import Location,SeedImportBatch
from apps.locations.seeding import import_public_portfolio
from apps.locations.service import update_location,confirm_location
from backend.tests.test_accounts import member

pytestmark=pytest.mark.django_db


def test_imports_36_unconfirmed_owned_locations_with_real_provenance():
    sync_catalog();result=import_public_portfolio()
    assert result.created==36 and result.existing==0
    assert Location.objects.count()==36 and not Location.objects.filter(confirmed=True).exists()
    assert set(Location.objects.values_list('status',flat=True))=={'owned'}
    assert all(l.source_url.startswith('https://paragonct.com/properties/') and l.gla_sqft is None for l in Location.objects.all())
    assert Location.objects.get(seed_id='P21').current_revision.method=='unplaced'
    staple=Location.objects.get(seed_id='P03')
    assert staple.current_revision.method=='seed_reference' and not staple.current_revision.confirmed
    assert staple.current_revision.lat==41.126611
    assert staple.seed_batch_id==result.batch.id
    assert 'OpenStreetMap' in Location.objects.get(seed_id='P20').current_revision.context['coordinate_attribution']


def test_repeat_import_never_overwrites_edits_confirmation_or_archive():
    sync_catalog();first=import_public_portfolio();user,_=member()
    item=Location.objects.get(seed_id='P03')
    item=update_location(location_id=item.pk,expected_version=1,attributes={'name':'User-maintained name','status':'archived'},actor=user)
    confirm_location(location_id=item.pk,expected_version=2,actor=user)
    second=import_public_portfolio()
    assert second.created==0 and second.existing==36 and second.batch.id==first.batch.id
    item.refresh_from_db()
    assert item.name=='User-maintained name' and item.status=='archived' and item.confirmed
    assert item.revisions.count()==1 and SeedImportBatch.objects.count()==1


def test_incomplete_seed_fails_before_any_property_is_written(tmp_path):
    sync_catalog()
    lines=Path('data/seed/paragon_public_properties.csv').read_text().splitlines()
    path=tmp_path/'incomplete.csv';path.write_text('\n'.join(lines[:-1])+'\n')
    with pytest.raises(ValueError,match='P01 through P36'):import_public_portfolio(path)
    assert not Location.objects.exists() and not SeedImportBatch.objects.exists()


def test_listing_demographics_traffic_and_financial_claims_are_not_imported():
    sync_catalog();import_public_portfolio()
    for item in Location.objects.select_related('current_revision'):
        assert item.gla_sqft is None and item.notes==''
        assert 'public_facts_as_listed' not in item.source_context
        assert 'notes' not in item.current_revision.context


@pytest.mark.django_db(transaction=True)
def test_concurrent_imports_create_one_portfolio_and_one_batch():
    from concurrent.futures import ThreadPoolExecutor
    from django.db import connection,connections
    if connection.vendor!='postgresql':pytest.skip('Seed import serialization requires PostgreSQL')
    sync_catalog()
    def load(_):
        try:return import_public_portfolio().created
        finally:connections.close_all()
    with ThreadPoolExecutor(max_workers=2) as pool:counts=list(pool.map(load,range(2)))
    assert sorted(counts)==[0,36]
    assert Location.objects.count()==36 and SeedImportBatch.objects.count()==1
