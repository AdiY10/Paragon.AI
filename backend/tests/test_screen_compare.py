"""T6 Screen (FR-25) and T7 Compare (FR-27)."""
from datetime import timedelta
from pathlib import Path
import pytest
from django.utils import timezone
from apps.insights import screens
from apps.locations.models import Location
from apps.operations.models import JobRun
from backend.tests.test_signals import placed, section, economy

pytestmark = pytest.mark.django_db
CENSUS = Path('tests/fixtures/real/census_geocoder')


def member(client):
    from django.contrib.auth import get_user_model
    from apps.accounts.models import Membership
    from apps.sources.catalog import sync_catalog
    sync_catalog()
    user = get_user_model().objects.create_user(username='m@example.org', email='m@example.org')
    Membership.objects.create(email='m@example.org', user=user, role='member')
    client.force_login(user)
    return user


def census(name):
    from apps.locations.census import parse_census, CensusCapture
    from datetime import datetime, timezone as tz
    import hashlib
    raw = (CENSUS / f'{name}.json').read_bytes()
    return lambda address: CensusCapture(parse_census(raw), raw, hashlib.sha256(raw).hexdigest(), datetime.now(tz.utc))


def test_screen_with_exact_match_pins_and_queues_computations(client, tmp_path, settings):
    settings.SOURCE_ARTIFACT_ROOT = tmp_path / 'artifacts'
    user = member(client)
    location, lookup, status, jobs = screens.create_screen(address='444 Westport Avenue, Norwalk, CT', name='',
        actor=user, geocoder=census('norwalk'))
    assert status == 'matched' and location.screening is True and location.status == 'candidate'
    assert location.current_revision.lat == pytest.approx(41.12661, abs=1e-4)
    assert [j.kind for j in JobRun.objects.all()] == ['analyze_location'] and jobs == [str(JobRun.objects.get().pk)]
    # Unsaved screens are not monitored and not in the portfolio list.
    from apps.area.refresh import monitored
    assert location not in list(monitored())
    assert client.get('/api/locations/?status=candidate').json()['count'] == 0
    assert client.get('/api/screens/').json()['results'][0]['id'] == str(location.pk)
    saved = client.post(f'/api/screens/{location.pk}/save/').json()
    assert saved['screening'] is False and location.pk in [l.pk for l in monitored()]


def test_ambiguous_or_missing_address_needs_a_pin_and_queues_nothing(client, tmp_path, settings):
    settings.SOURCE_ARTIFACT_ROOT = tmp_path / 'artifacts'
    user = member(client)
    location, _, status, jobs = screens.create_screen(address='445 Main Street, Mount Kisco, NY', name='Deal',
        actor=user, geocoder=census('mount_kisco'))
    assert status == 'ambiguous' and location.current_revision.lat is None and jobs == []
    assert not JobRun.objects.exists()
    assert client.post(f'/api/locations/{location.pk}/compute/').status_code == 404  # manual compute removed (B3a)
    assert client.post(f'/api/locations/{location.pk}/area/').status_code == 400


def test_old_unsaved_screens_expire(client):
    user = member(client)
    loc = placed('Old screen', status='candidate')
    Location.objects.filter(pk=loc.pk).update(screening=True, created_at=timezone.now() - timedelta(days=31))
    assert screens.expire_screens() == 1 and Location.objects.get(pk=loc.pk).status == 'archived'


def test_screen_api_validates_input(client):
    member(client)
    assert client.post('/api/screens/', {'address': ''}, content_type='application/json').status_code == 400


def test_compare_rows_portfolio_columns_and_directional_highlighting(client):
    member(client)
    a, b, c = placed('A', 41.1), placed('B', 41.2), placed('C', 41.3)
    section(a, 'economy', economy(priv=0.04, unemp=-0.2))
    section(b, 'economy', economy(priv=-0.01, unemp=0.5))
    section(c, 'economy', economy(priv=0.01, unemp=0.1))
    section(a, 'hazards', {'flood_at_pin': {'zone': 'AE', 'sfha': True}, 'flood_nearby': {}, 'nri': {'rating': 'Very Low'}, 'concerns': []})
    body = client.get(f'/api/compare/?ids={a.pk},{b.pk},{c.pk}').json()
    assert [l['name'] for l in body['locations']] == ['A', 'B', 'C']
    assert body['locations'][0]['sfha'] is True and body['locations'][0]['flood_zone'] == 'AE'
    priv = next(r for r in body['rows'] if r['key'] == 'private_jobs_yoy')
    assert priv['cells'][str(a.pk)]['best'] and priv['cells'][str(b.pk)]['worst']
    unemp = next(r for r in body['rows'] if r['key'] == 'unemployment_change')
    assert unemp['cells'][str(a.pk)]['best'] and unemp['cells'][str(b.pk)]['worst']  # lower is better
    assert priv['portfolio']['median'] == pytest.approx(0.01) and priv['portfolio']['n'] == 3
    pop = next(r for r in body['rows'] if r['key'] == 'population')
    assert all(cell['value'] is None and not cell['best'] for cell in pop['cells'].values())
    assert client.get(f'/api/compare/?ids={a.pk}').status_code == 400
    assert client.get('/api/compare/?ids=nope,also-nope').status_code == 400
