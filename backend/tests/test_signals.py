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
    from apps.area.service import SECTION_LOGIC
    import uuid
    return AreaSection.objects.create(location=loc, revision=loc.current_revision, analysis_version=loc.analysis_version,
        section=name, status=status, data=data, sources=[], snapshot_ids=[], inputs_sha256=uuid.uuid4().hex,
        logic_version=SECTION_LOGIC.get(name, 1))  # as computed by the current code


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
    assert engine.evaluate(loc, today=TODAY) == (5, 0, 0)
    got = {s.rule_id: s.severity for s in Signal.objects.filter(location=loc)}
    # B7a: actionable changes only, High/Watch only. Nearby jobs (SIG-06), permits (SIG-07), openings
    # (SIG-10) and the static flood zone (SIG-11, now a risk badge) stay in the analysis.
    assert got == {'SIG-03': 'Watch', 'SIG-04': 'Watch', 'SIG-05': 'Watch', 'SIG-08': 'Watch', 'SIG-09': 'Watch'}
    assert all(s.next_step for s in Signal.objects.all())
    assert engine.attention(loc.pk) == 'Watch'
    assert engine.risk_badges(loc) == [{'kind': 'flood', 'level': 'inside', 'source': 'SRC-11',
        'label': 'Inside FEMA high-risk flood zone AE (base flood elevation 9 ft)'}]
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
    assert status['SIG-09'][0] == 'expired' and status['SIG-08'][0] == 'active'


def test_pin_move_resolves_as_location_corrected():
    from apps.locations.service import change_pin
    loc = placed()
    all_sections(loc)
    engine.evaluate(loc, today=TODAY)
    loc = change_pin(location_id=loc.pk, expected_version=loc.version, lat=41.2, lon=-73.5, actor=None)
    engine.evaluate(loc, today=TODAY)
    assert set(Signal.objects.values_list('resolved_reason', flat=True)) == {'location corrected'}
    assert engine.attention(loc.pk) == 'Clear'


def test_demographic_trends_are_analysis_context_not_alerts(monkeypatch):
    loc = placed()

    class Demo:
        acs_year = 2024
        rings = [{'radius_miles': 3, 'trends': {
            'population_change': {'value': -0.04, 'significant': True, 'period': '2015–2019 → 2020–2024', 'baseline': 100, 'current': 96, 'z': 2.1},
            'real_mean_income_change': {'value': 0.08, 'significant': False}}}]
    monkeypatch.setattr('apps.demographics.service.current_result', lambda l: Demo)
    engine.evaluate(loc, today=TODAY)
    assert not Signal.objects.exists()  # B7a: shown in the analysis, never alerted


def test_api_ranking_review_dismiss_and_escalation_reopens(client):
    from django.contrib.auth import get_user_model
    from apps.accounts.models import Membership
    user = get_user_model().objects.create_user(username='m@example.org', email='m@example.org')
    Membership.objects.create(email='m@example.org', user=user, role='member')
    client.force_login(user)
    loc = placed()
    all_sections(loc)
    engine.evaluate(loc, today=TODAY)
    body = client.get('/api/signals/').json()
    results = body['results']
    assert results[0]['rule_id'] == 'SIG-09' and {r['severity'] for r in results} == {'Watch'}
    assert all(r['next_step'] for r in results)
    assert client.get(f'/api/locations/{loc.pk}/').json()['attention'] == 'Watch'
    assert [g['rule_id'] for g in body['groups']] == [r['rule_id'] for r in results]  # one property: no merging
    closure = next(r for r in results if r['rule_id'] == 'SIG-09')
    assert client.post(f"/api/signals/{closure['id']}/review/", {'action': 'dismissed', 'note': 'Verified open'},
        content_type='application/json').status_code == 200
    engine.evaluate(loc, today=TODAY)
    assert Signal.objects.get(pk=closure['id']).status == 'dismissed'
    # Escalation (it turns out to be the tenant's own store -> High) reopens a dismissed signal.
    from apps.area.models import AreaSection
    from apps.locations.models import Tenant
    Tenant.objects.create(location=loc, name='Regal Cinemas', normalized_key='regal cinemas', origin='user')
    data = AreaSection.objects.filter(section='businesses').latest('computed_at').data
    data['changes']['closures'][0]['distance_mi'] = 0.05
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
    # Inside zone AE is a standing risk: a badge on the analysis, not an alert (B7a).
    assert not Signal.objects.filter(location=loc).exists()
    assert engine.risk_badges(loc)[0]['label'].startswith('Inside FEMA high-risk flood zone AE')
    king = placed('Kingston Marketplace', *KPIN)
    monkeypatch.setattr('apps.area.overture.available_releases', lambda opener=None: ['2026-09-23.1', '2026-10-21.0'])
    compute_area(king.pk, sections=('businesses',), capturer=lambda lat, lon, r: json.dumps(kingston(r)).encode())
    engine.evaluate(king, today=TODAY)
    regal = Signal.objects.get(location=king, rule_id='SIG-09', title__contains='Regal Cinemas')
    assert regal.severity == 'Watch' and regal.evidence['evidence'] == 'marked permanently closed'


# ---- R2 item 5: stable identity and lifecycle -----------------------------------------

def test_new_data_period_updates_the_same_alert_and_keeps_dismissal():
    loc = placed()
    section(loc, 'economy', economy())
    engine.evaluate(loc, today=TODAY)
    s05 = Signal.objects.get(rule_id='SIG-05')
    assert s05.subject == 'county:36111:unemployment'
    s05.status = 'dismissed'
    s05.save()
    later = economy()
    later['unemployment'] = {**later['unemployment'], 'period': '2026-10', 'change_pts': 1.3}
    section(loc, 'economy', later)
    engine.evaluate(loc, today=TODAY)
    rows = Signal.objects.filter(rule_id='SIG-05')
    assert rows.count() == 1 and rows[0].status == 'dismissed' and rows[0].period == '2026-10'
    assert Signal.objects.filter(rule_id='SIG-03').count() == 1


def test_reappearing_condition_starts_a_new_episode():
    loc = placed()
    section(loc, 'economy', economy())
    engine.evaluate(loc, today=TODAY)
    first = Signal.objects.get(rule_id='SIG-04')
    section(loc, 'economy', economy(retail=0.0))
    engine.evaluate(loc, today=TODAY)
    assert Signal.objects.get(pk=first.pk).status == 'resolved'
    section(loc, 'economy', economy(retail=-0.06))
    engine.evaluate(loc, today=TODAY)
    again = Signal.objects.get(pk=first.pk)
    assert again.status == 'active' and again.episode == 2
    assert again.first_evidence['value'] == -0.06 and again.episode_started_at > first.episode_started_at


def test_missing_inputs_never_resolve_alerts():
    loc = placed()
    all_sections(loc)
    engine.evaluate(loc, today=TODAY)
    section(loc, 'traffic', {}, status='unavailable')  # newer row for the same version wins
    engine.evaluate(loc, today=TODAY)
    assert Signal.objects.get(rule_id='SIG-08').status == 'active'


def test_event_alerts_stay_until_the_window_ends_even_when_not_in_the_latest_diff():
    loc = placed()
    all_sections(loc)
    engine.evaluate(loc, today=TODAY)
    section(loc, 'businesses', {'release': '2026-12-17.0', 'prior_release': '2026-11-18.0', 'changes': {}})
    engine.evaluate(loc, today=date(2026, 12, 20))
    assert Signal.objects.get(rule_id='SIG-09').status == 'active'
    engine.evaluate(loc, today=date(2027, 3, 1))
    assert Signal.objects.get(rule_id='SIG-09').status == 'expired'


def test_migration_collapses_period_keyed_duplicates():
    import importlib
    from django.apps import apps as django_apps
    mig = importlib.import_module('apps.insights.migrations.0005_rekey_signal_subjects')
    loc = placed()
    section(loc, 'economy', economy())
    common = dict(location=loc, rule_id='SIG-05', category='Economy', severity='Watch', direction='negative',
        title='t', why='w', analysis_version=loc.analysis_version)
    Signal.objects.create(subject='laus:2026-08', status='dismissed', **common)
    Signal.objects.create(subject='laus:2026-09', status='active', **common)
    Signal.objects.create(subject='overture:abc', **{**common, 'rule_id': 'SIG-09', 'category': 'Closure'})
    mig.forwards(django_apps, None)
    rows = list(Signal.objects.filter(rule_id='SIG-05'))
    assert len(rows) == 1 and rows[0].status == 'dismissed' and rows[0].subject == 'county:36111:unemployment'
    assert Signal.objects.get(rule_id='SIG-09').subject == 'place:abc'


def test_review_feedback_and_reopen(client):
    from backend.tests.test_accounts import member
    loc = placed()
    all_sections(loc)
    engine.evaluate(loc, today=TODAY)
    user, _ = member()
    client.force_login(user)
    s = Signal.objects.get(rule_id='SIG-09')
    url = f'/api/signals/{s.pk}/review/'
    body = client.post(url, {'action': 'dismissed', 'note': 'Regal still open', 'feedback': 'not_useful'},
        content_type='application/json').json()
    assert body['status'] == 'dismissed' and body['feedback'] == 'not_useful' and body['reviewed'] is True
    assert client.post(url, {'action': 'reopened'}, content_type='application/json').json()['status'] == 'active'
    assert client.post(url, {'action': 'feedback', 'feedback': 'maybe'}, content_type='application/json').status_code == 400
    assert Signal.objects.get(pk=s.pk).review_note == 'Regal still open'
