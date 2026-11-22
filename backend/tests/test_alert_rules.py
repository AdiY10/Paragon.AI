"""Redesign B7b: competing grocer (SIG-14), flood-zone change (SIG-11), county economy (SIG-15), alert quality."""
from datetime import timedelta
import pytest
from apps.area import businesses as biz
from apps.insights import signals as engine
from apps.insights.models import Signal
from backend.tests.test_signals import placed, section, economy, TODAY

pytestmark = pytest.mark.django_db
CENTER = (41.0, -73.0)


def place(pid, name, brand=None, cat='supermarket', dlat=0.01, conf=0.95, status='open'):
    return {'id': pid, 'name': name, 'brand': brand, 'basic_category': cat, 'confidence': conf,
        'operating_status': status, 'lat': CENTER[0] + dlat, 'lon': CENTER[1]}


def test_new_grocer_needs_two_releases():
    aldi = place('a1', 'ALDI', 'ALDI')
    older, prior, current = [], [aldi], [aldi]
    assert [g['id'] for g in biz.new_grocers(older, prior, current, CENTER)] == ['a1']
    assert biz.new_grocers([], [], [aldi], CENTER) == []          # only in the latest release: not yet
    assert biz.new_grocers([aldi], [aldi], [aldi], CENTER) == []  # already there before
    far = place('a2', 'ALDI', 'ALDI', dlat=0.05)                  # ~3.5 mi
    assert biz.new_grocers([], [far], [far], CENTER) == []
    cafe = place('c1', 'Cafe', cat='cafe')
    assert biz.new_grocers([], [cafe], [cafe], CENTER) == []


def grocer_section(loc, name='ALDI'):
    section(loc, 'businesses', {'release': '2026-11-18.0', 'changes': {'closures': [], 'openings': [],
        'new_grocers': [{'id': 'a1', 'name': name, 'brand': name, 'category': 'supermarket', 'distance_mi': 1.2}]}})


def test_competing_grocer_alerts_only_a_center_with_another_grocer():
    from apps.locations.models import Tenant
    loc = placed()
    grocer_section(loc)
    engine.evaluate(loc, today=TODAY)
    assert not Signal.objects.exists()  # no grocery tenant: not a competitor of ours
    Tenant.objects.create(location=loc, name='Stop & Shop', normalized_key='stop shop', origin='user')
    engine.evaluate(loc, today=TODAY)
    s = Signal.objects.get(rule_id='SIG-14')
    assert s.severity == 'Watch' and s.title == 'New competing grocer nearby: ALDI (1.2 mi)' and s.next_step
    other = placed('Other')
    Tenant.objects.create(location=other, name='ALDI', normalized_key='aldi', origin='user')
    grocer_section(other)
    engine.evaluate(other, today=TODAY)
    assert not other.signals.exists()  # the same brand as our grocer


def hazards(loc, zone, inside):
    return section(loc, 'hazards', {'flood_at_pin': {'zone': zone, 'sfha': inside, 'in_sfha': inside, 'bfe_ft': 9.0 if inside else None},
        'flood_nearby': {}, 'nri': {}})


def test_flood_zone_change_into_high_risk_is_high():
    from apps.area.models import AreaSection
    loc = placed()
    first = hazards(loc, 'X', False)
    engine.evaluate(loc, today=TODAY)
    assert not Signal.objects.exists()
    second = hazards(loc, 'AE', True)
    AreaSection._base_manager.filter(pk=first.pk).update(computed_at=second.computed_at - timedelta(days=30))
    engine.evaluate(loc, today=TODAY)
    s = Signal.objects.get(rule_id='SIG-11')
    assert s.severity == 'High' and s.subject == 'flood:zone_change' and 'now in high-risk zone AE (was X)' in s.title
    assert engine.attention(loc.pk) == 'High'


def test_standing_flood_zone_is_never_an_alert():
    loc = placed()
    hazards(loc, 'AE', True)
    engine.evaluate(loc, today=TODAY)
    assert not Signal.objects.exists() and engine.risk_badges(loc)[0]['level'] == 'inside'


@pytest.mark.parametrize('kwargs,alert', [
    ({'priv': -0.03, 'retail': -0.05, 'unemp': 1.2}, True),   # three conditions
    ({'priv': -0.03, 'retail': 0.0, 'unemp': 0.0}, False),    # one condition
    ({'priv': -0.045, 'retail': 0.0, 'unemp': 0.0}, True),    # a sharp private-jobs drop on its own
    ({'priv': 0.0, 'retail': -0.05, 'unemp': 1.0}, True),     # retail + unemployment
])
def test_county_economy_is_one_alert(kwargs, alert):
    loc = placed()
    section(loc, 'economy', economy(**kwargs))
    engine.evaluate(loc, today=TODAY)
    assert [s.rule_id for s in Signal.objects.all()] == (['SIG-15'] if alert else [])


def test_old_county_alerts_retire():
    loc = placed()
    s = Signal.objects.create(location=loc, rule_id='SIG-05', subject='county:36111:unemployment', category='Economy',
        severity='Watch', direction='negative', title='x', why='', analysis_version=loc.analysis_version)
    section(loc, 'economy', economy(priv=0.0, retail=0.0))
    engine.evaluate(loc, today=TODAY)
    s.refresh_from_db()
    assert s.status == 'retired'


def test_alert_quality_endpoint(client):
    from backend.tests.test_accounts import member
    loc = placed()
    for i, fb in enumerate(['useful', 'useful', 'not_useful', '']):
        Signal.objects.create(location=loc, rule_id='SIG-09', subject=f'place:{i}', category='Closure', severity='Watch',
            direction='negative', title='x', why='', analysis_version=1, feedback=fb)
    user, _ = member()
    client.force_login(user)
    assert client.get('/api/admin/alert-quality/').status_code == 403
    admin, _ = member('admin@example.org', 'admin')
    client.force_login(admin)
    assert client.get('/api/admin/alert-quality/').json() == [
        {'rule_id': 'SIG-09', 'total': 4, 'useful': 2, 'not_useful': 1, 'precision': 0.67}]


def test_traffic_decline_needs_counts_close_in_time():
    def roads(prior_count_year):
        return {'roads': [{'label': 'Birch St', 'aadt': 4195, 'year': 2025, 'prior_aadt': 4905, 'prior_year': 2024,
            'change_pct': -0.145, 'count_year': 2025, 'prior_count_year': prior_count_year}]}
    loc = placed()
    section(loc, 'traffic', roads(2014))  # an 11-year drift is not a recent change
    engine.evaluate(loc, today=TODAY)
    assert not Signal.objects.exists()
    section(loc, 'traffic', roads(2022))
    engine.evaluate(loc, today=TODAY)
    assert Signal.objects.get(rule_id='SIG-08').title == 'Traffic on Birch St −14.5% (counts 2022 → 2025)'
