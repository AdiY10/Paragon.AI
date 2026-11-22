"""Redesign B5: analyze a new place by address or map point; keep/expiry; caps; host allowlist."""
from datetime import timedelta
import pytest
from django.utils import timezone
from apps.insights import screens
from apps.locations.models import Location
from apps.operations.models import JobRun
from backend.tests.test_screen_compare import member, census

pytestmark = pytest.mark.django_db
KISCO = {'state': 'NY', 'state_fips': '36', 'county': 'Westchester County', 'county_fips': '36119', 'place': 'Mount Kisco'}


@pytest.fixture
def point(monkeypatch):
    calls = []

    def fake(lat, lon):
        calls.append((lat, lon))
        return None if lon > -60 else KISCO
    monkeypatch.setattr('apps.locations.census.fetch_point_geographies', fake)
    return calls


def test_map_point_creates_a_named_pinned_place_and_queues_it(client, point, tmp_path, settings):
    settings.SOURCE_ARTIFACT_ROOT = tmp_path
    member(client)
    r = client.post('/api/analyses/', {'lat': 41.2041, 'lon': -73.7271}, content_type='application/json')
    assert r.status_code == 201
    body = r.json()
    loc = Location.objects.get(pk=body['location']['id'])
    assert loc.name == 'Near Mount Kisco, NY' and loc.address == 'Map point 41.20410, -73.72710'
    assert loc.screening and loc.status == 'candidate' and loc.state == 'NY'
    assert loc.current_revision.method == 'manual' and loc.current_revision.lat == pytest.approx(41.2041)
    job = JobRun.objects.get(pk=body['analysis']['job_id'])
    assert job.kind == 'analyze_location' and body['analysis']['state'] == 'queued'


@pytest.mark.parametrize('lat,lon', [(48.85, 2.35), (30.0, -40.0), (95, 0)])
def test_points_outside_the_us_are_refused(client, point, lat, lon):
    member(client)
    r = client.post('/api/analyses/', {'lat': lat, 'lon': lon}, content_type='application/json')
    assert r.status_code == 400 and not Location.objects.exists()


def test_a_point_still_works_when_the_name_lookup_fails(client, monkeypatch):
    from apps.locations.census import GeocoderError

    def down(lat, lon):
        raise GeocoderError('TIMEOUT')
    monkeypatch.setattr('apps.locations.census.fetch_point_geographies', down)
    member(client)
    r = client.post('/api/analyses/', {'lat': 26.546, 'lon': -81.8767, 'label': 'Corner lot'}, content_type='application/json')
    assert r.status_code == 201 and r.json()['location']['name'] == 'Corner lot'
    r = client.post('/api/analyses/', {'lat': 26.5, 'lon': -81.8}, content_type='application/json')
    assert r.json()['location']['name'] == 'Map point 26.50000, -81.80000'


def test_address_flows_follow_part_c(client, monkeypatch, tmp_path, settings):
    settings.SOURCE_ARTIFACT_ROOT = tmp_path / 'a'
    member(client)
    monkeypatch.setattr('apps.locations.geocoding.fetch_census', census('norwalk'))
    r = client.post('/api/analyses/', {'address': '444 Westport Avenue, Norwalk, CT'}, content_type='application/json')
    assert r.status_code == 201 and r.json()['geocode']['status'] == 'matched' and r.json()['analysis']['job_id']
    monkeypatch.setattr('apps.locations.geocoding.fetch_census', census('mount_kisco'))
    r = client.post('/api/analyses/', {'address': '445 Main Street, Mount Kisco, NY'}, content_type='application/json')
    g = r.json()['geocode']
    assert r.status_code == 200 and g['status'] == 'ambiguous' and len(g['candidates']) >= 2
    assert {'index', 'matched_address', 'lat', 'lon'} <= set(g['candidates'][0]) and g['lookup_id']


def test_geocoder_down_asks_for_a_pin(client, monkeypatch):
    from apps.locations.census import GeocoderError

    def down(address, **kw):
        raise GeocoderError('TIMEOUT')
    monkeypatch.setattr('apps.locations.geocoding.fetch_census', down)
    member(client)
    r = client.post('/api/analyses/', {'address': '1 Nowhere Rd, Anytown, CT'}, content_type='application/json')
    assert r.status_code == 503 and r.json()['geocode']['status'] == 'unavailable' and r.json()['next'] == 'place_pin'


def test_a_global_cap_returns_retry_after(client, point):
    member(client)
    for i in range(screens.MAX_LIVE_ANALYSES):
        JobRun.objects.create(kind='analyze_location', scope=f's{i}', dedup_key=f'k{i}', queue='paragon-foreground')
    r = client.post('/api/analyses/', {'lat': 41.2, 'lon': -73.7}, content_type='application/json')
    assert r.status_code == 429 and r.json()['retry_after'] == 30 and r['Retry-After'] == '30'


def test_keep_list_and_ninety_day_expiry(client, point):
    member(client)
    a = client.post('/api/analyses/', {'lat': 41.2, 'lon': -73.7}, content_type='application/json').json()['location']['id']
    b = client.post('/api/analyses/', {'lat': 41.3, 'lon': -73.8}, content_type='application/json').json()['location']['id']
    kept = client.post(f'/api/analyses/{a}/keep/', {'kept': True}, content_type='application/json').json()
    assert kept == {'kept': True, 'expires_at': None}
    rows = client.get('/api/analyses/').json()
    assert [r['id'] for r in rows] == [b, a] and rows[1]['kept'] and rows[0]['expires_at']
    assert rows[0]['state'] in ('running', 'partial') and rows[0]['lat'] == pytest.approx(41.3)
    old = timezone.now() - timedelta(days=91)
    Location.objects.filter(pk__in=[a, b]).update(created_at=old)
    screens.expire_screens()
    assert Location.objects.get(pk=a).status == 'candidate' and Location.objects.get(pk=b).status == 'archived'
    assert Location.objects.filter(pk=b).exists()  # archived, never deleted
    assert client.post(f'/api/analyses/{a}/keep/', {'kept': 'yes'}, content_type='application/json').status_code == 400


def test_new_places_never_raise_alerts(point):
    from apps.insights import signals as engine
    from backend.tests.test_signals import section, economy, TODAY
    from django.contrib.auth import get_user_model
    user = get_user_model().objects.create_user(username='u@example.org', email='u@example.org')
    loc, _ = screens.create_point_screen(lat=41.2, lon=-73.7, actor=user)
    section(loc, 'economy', economy())
    engine.evaluate(loc, today=TODAY)
    assert not loc.signals.exists()


# ---- outbound host allowlist -----------------------------------------------------

def test_only_public_data_hosts_are_reachable():
    from urllib.request import Request
    from apps.area import http
    for host in ('tigerweb.geo.census.gov', 'www2.census.gov', 'api.bls.gov', 'hazards.fema.gov', 'geo.dot.gov',
            'efts.sec.gov', 'services.arcgis.com', 'overturemaps-us-west-2.s3.us-west-2.amazonaws.com'):
        assert http.host_allowed(host), host
    for host in ('example.com', 'census.gov.evil.com', 'evilcensus.gov', 'arcgis.com', None):
        assert not http.host_allowed(host), host
    with pytest.raises(http.HostNotAllowed):  # refused before any connection is made
        http.default_opener().open(Request('https://example.com/?lat=41.1&lon=-73.4'), timeout=1)
    with pytest.raises(http.SourceError):
        http.fetch('https://example.com/', retries=0)
