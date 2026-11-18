import pytest
from apps.locations.models import Location
from apps.sources.catalog import sync_catalog
from apps.locations.seeding import import_public_portfolio
from backend.tests.test_accounts import member

pytestmark=pytest.mark.django_db


def signed_in(client):
    user,_=member();client.force_login(user);return user


def new_location(client):
    response=client.post('/api/locations/',{'name':'User-entered location','address':'444 Westport Avenue, Norwalk, CT'},content_type='application/json')
    assert response.status_code==201
    return response.json()


def test_locations_and_history_require_authentication(client):
    assert client.get('/api/locations/').status_code==403
    assert client.post('/api/locations/',{}).status_code==403


def test_member_can_create_and_inspect_unplaced_candidate(client):
    signed_in(client);data=new_location(client)
    assert data['status']=='candidate' and not data['confirmed']
    assert data['current_revision']['lat'] is None and data['gla_sqft'] is None
    assert client.get(f"/api/locations/{data['id']}/").json()['id']==data['id']


def test_real_portfolio_is_searchable_filterable_and_unconfirmed(client):
    signed_in(client);sync_catalog();import_public_portfolio()
    data=client.get('/api/locations/').json()
    assert data['count']==36 and not any(item['confirmed'] for item in data['results'])
    assert client.post('/api/locations/search/',{'q':'Staples'},content_type='application/json').json()['count']==1
    assert client.get('/api/locations/?state=NY').json()['count']==5


def test_confirm_edit_archive_and_history_preserve_provenance(client):
    user=signed_in(client);data=new_location(client);path=f"/api/locations/{data['id']}/"
    confirmed=client.post(path+'confirm/',{'expected_version':1},content_type='application/json')
    assert confirmed.status_code==200 and confirmed.json()['confirmed']
    changed=client.patch(path,{'expected_version':2,'name':'Edited by member','status':'archived'},content_type='application/json')
    assert changed.status_code==200 and changed.json()['version']==3
    assert client.get('/api/locations/').json()['count']==0
    assert client.get('/api/locations/?status=archived').json()['count']==1
    events=client.get(path+'history/').json()['results']
    assert events[0]['actor']==user.email and events[0]['action']=='attributes_changed'


def test_pin_edit_creates_revision_and_stale_save_returns_conflict(client):
    signed_in(client);data=new_location(client);path=f"/api/locations/{data['id']}/"
    changed=client.post(path+'pin/',{'expected_version':1,'lat':41.126611,'lon':-73.388299,'confirmed':True},content_type='application/json')
    assert changed.status_code==200 and changed.json()['current_revision']['method']=='manual'
    assert changed.json()['analysis_version']==2
    stale=client.patch(path,{'expected_version':1,'notes':'stale save'},content_type='application/json')
    assert stale.status_code==409
    assert Location.objects.get(pk=data['id']).notes==''


def test_confirmation_and_pin_method_cannot_be_forged_as_editable_fields(client):
    signed_in(client);data=new_location(client);path=f"/api/locations/{data['id']}/"
    assert client.patch(path,{'expected_version':1,'confirmed':True},content_type='application/json').status_code==400
    assert client.post(path+'pin/',{'expected_version':1,'lat':41,'lon':-73,'method':'census_exact'},content_type='application/json').status_code==400


def test_missing_version_and_boolean_pin_are_rejected(client):
    signed_in(client);data=new_location(client);path=f"/api/locations/{data['id']}/"
    assert client.patch(path,{'notes':'missing version'},content_type='application/json').status_code==400
    assert client.post(path+'pin/',{'expected_version':1,'lat':True,'lon':-73},content_type='application/json').status_code==400


def test_browser_mutations_require_csrf():
    from django.test import Client
    client=Client(enforce_csrf_checks=True);signed_in(client)
    assert client.post('/api/locations/',{'name':'Private','address':'Address'}).status_code==403


def test_search_text_is_accepted_in_request_body_only(client):
    signed_in(client);data=new_location(client)
    assert client.get('/api/locations/?q=Westport').status_code==400
    response=client.post('/api/locations/search/',{'q':'Westport'},content_type='application/json')
    assert response.status_code==200 and response.json()['results'][0]['id']==data['id']
