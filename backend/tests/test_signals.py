"""T4: deterministic signal engine (docs/04 §5)."""
from datetime import date
import json
import pytest
from apps.insights.models import Signal
from apps.insights import signals as engine

pytestmark = pytest.mark.django_db
TODAY = date(2026, 11, 19)


def placed(name='Center', lat=41.1, lon=-73.4, status='owned'):
    from apps.locations.service import create_location, change_pin
    loc = create_location(name=name, address='1 Main St', actor=None)
    loc.status = status
    loc.save()
    return change_pin(location_id=loc.pk, expected_version=loc.version, lat=lat, lon=lon, actor=None)


def section(loc, name, data, status='available'):
    from apps.area.models import AreaSection
    import uuid
    return AreaSection.objects.create(location=loc, revision=loc.current_revision, analysis_version=loc.analysis_version,
        section=name, status=status, data=data, sources=[], snapshot_ids=[], inputs_sha256=uuid.uuid4().hex)


def economy(priv=-0.03, retail=-0.05, unemp=1.2, permits=0.4, units=100):
    return {'county': {'fips': '36111', 'name': 'Ulster County'},
        'employment': {'period': '2026 Q1', 'private': {'value': 47000, 'yoy_pct': priv}, 'retail': {'value': 8000, 'yoy_pct': retail}},
        'unemployment': {'rate': 0.05, 'prior_rate': 0.038, 'change_pts': unemp, 'period': '2026-09', 'preliminary': True},
        'permits': {'value': 500, 'prior': 500 - units, 'change': units, 'change_pct': permits, 'period': '12 months to 2026-09'}}


def all_sections(loc):
    section(loc, 'economy', economy())
    section(loc, 'jobs', {'year': 2024, 'prior_year': 2023, 'rings': [{'radius_miles': 3, 'total': 9400, 'prior_total': 10000, 'change_pct': -0.06}]})
    section(loc, 'traffic', {'roads': [{'label': 'Route 1', 'aadt': 18000, 'year': 2025, 'prior_aadt': 20200, 'prior_year': 2024, 'change_pct': -0.12}]})
    section(loc, 'hazards', {'flood_at_pin': {'zone': 'AE', 'sfha': True, 'bfe_ft': 9.0, 'dfirm_id': '12071C'}, 'flood_nearby': {}, 'nri': {}})
    section(loc, 'businesses', {'release': '2026-11-18.0', 'prior_release': '2026-10-21.0', 'changes': {
        'closures': [{'id': 'p1', 'name': 'Regal Cinemas', 'severity': 'Watch', 'distance_mi': 0.25, 'evidence': 'marked permanently closed', 'category': 'movie_theater'}],
        'openings': [{'id': 'p2', 'name': 'ALDI', 'severity': 'FYI', 'distance_mi': 1.2, 'category': 'food_and_beverage_store'}]}})


def test_rules_fire_with_expected_severity_and_attention():
    loc = placed()
    all_sections(loc)
    assert engine.evaluate(loc, today=TODAY) == (9, 0, 0)
    got = {s.rule_id: s.severity for s in Signal.objects.filter(location=loc)}
    assert got == {'SIG-03': 'Watch', 'SIG-04': 'Watch', 'SIG-05': 'Watch', 'SIG-06': 'Watch', 'SIG-07': 'FYI',
        'SIG-08': 'Watch', 'SIG-09': 'Watch', 'SIG-10': 'FYI', 'SIG-11': 'High'}
    assert engine.attention(loc.pk) == 'High'
    s05 = Signal.objects.get(rule_id='SIG-05')
    assert '(preliminary)' in s05.title and s05.evidence['source_link'] == 'https://www.bls.gov/lau/'
    assert engine.evaluate(loc, today=TODAY) == (0, 0, 0)  # idempotent


def test_just_below_thresholds_do_not_fire():
    loc = placed()
    section(loc, 'economy', economy(priv=-0.019, retail=-0.039, unemp=0.9, permits=0.24, units=100))
    engine.evaluate(loc, today=TODAY)
    assert not Signal.objects.exists() and engine.attention(loc.pk) == 'Clear'


def test_conditions_clearing_resolve_and_events_expire():
    loc = placed()
    all_sections(loc)
    engine.evaluate(loc, today=TODAY)
    section(loc, 'economy', economy(priv=0.01, retail=0.0, unemp=0.1, permits=0.0, units=0))
    engine.evaluate(loc, today=date(2027, 3, 1))  # 103 days after the Overture release
    status = {s.rule_id: (s.status, s.resolved_reason) for s in Signal.objects.all()}
    assert status['SIG-03'] == ('resolved', 'condition no longer holds')
    assert status['SIG-09'][0] == 'expired' and status['SIG-11'][0] == 'active'


def test_pin_move_resolves_as_location_corrected():
    from apps.locations.service import change_pin
    loc = placed()
    all_sections(loc)
    engine.evaluate(loc, today=TODAY)
    loc = change_pin(location_id=loc.pk, expected_version=loc.version, lat=41.2, lon=-73.5, actor=None)
    engine.evaluate(loc, today=TODAY)
    assert set(Signal.objects.values_list('resolved_reason', flat=True)) == {'location corrected'}
    assert engine.attention(loc.pk) == 'Clear'


def test_demographic_trend_signals_need_significance(monkeypatch):
    loc = placed()

    class Demo:
        acs_year = 2024
        rings = [{'radius_miles': 3, 'trends': {
            'population_change': {'value': -0.04, 'significant': True, 'period': '2015–2019 → 2020–2024', 'baseline': 100, 'current': 96, 'z': 2.1},
            'real_mean_income_change': {'value': 0.08, 'significant': False}}}]
    monkeypatch.setattr('apps.demographics.service.current_result', lambda l: Demo)
    engine.evaluate(loc, today=TODAY)
    assert [(s.rule_id, s.severity, s.direction) for s in Signal.objects.all()] == [('SIG-01', 'Watch', 'negative')]


def test_api_ranking_review_dismiss_and_escalation_reopens(client):
    from django.contrib.auth import get_user_model
    from apps.accounts.models import Membership
    user = get_user_model().objects.create_user(username='m@example.org', email='m@example.org')
    Membership.objects.create(email='m@example.org', user=user, role='member')
    client.force_login(user)
    loc = placed()
    all_sections(loc)
    engine.evaluate(loc, today=TODAY)
    results = client.get('/api/signals/').json()['results']
    assert results[0]['rule_id'] == 'SIG-11' and [r['severity'] for r in results][:1] == ['High']
    assert client.get(f'/api/locations/{loc.pk}/').json()['attention'] == 'High'
    closure = next(r for r in results if r['rule_id'] == 'SIG-09')
    assert client.post(f"/api/signals/{closure['id']}/review/", {'action': 'dismissed', 'note': 'Verified open'},
        content_type='application/json').status_code == 200
    engine.evaluate(loc, today=TODAY)
    assert Signal.objects.get(pk=closure['id']).status == 'dismissed'
    # Escalation (tenant match -> High) reopens a dismissed signal.
    from apps.area.models import AreaSection
    data = AreaSection.objects.filter(section='businesses').latest('computed_at').data
    data['changes']['closures'][0]['severity'] = 'High'
    section(loc, 'businesses', data)
    engine.evaluate(loc, today=TODAY)
    assert Signal.objects.get(pk=closure['id']).status == 'active'
    client.logout()
    assert client.get('/api/signals/').status_code == 403


def test_real_cypress_lake_flood_and_kingston_regal_closure(tmp_path, client, settings, monkeypatch):
    from backend.tests.test_area_profile import setup, FixtureOpener, CYPRESS, KPIN, kingston
    from apps.area.service import compute_area
    loc = setup(tmp_path, client, *CYPRESS, settings)
    compute_area(loc.pk, sections=('hazards',), opener=FixtureOpener('cypress'))
    assert Signal.objects.get(location=loc, rule_id='SIG-11').severity == 'High'
    king = placed('Kingston Marketplace', *KPIN)
    monkeypatch.setattr('apps.area.overture.available_releases', lambda opener=None: ['2026-09-23.1', '2026-10-21.0'])
    compute_area(king.pk, sections=('businesses',), capturer=lambda lat, lon, r: json.dumps(kingston(r)).encode())
    engine.evaluate(king, today=TODAY)
    regal = Signal.objects.get(location=king, rule_id='SIG-09', title__contains='Regal Cinemas')
    assert regal.severity == 'Watch' and regal.evidence['evidence'] == 'marked permanently closed'
