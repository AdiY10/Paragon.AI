"""T5: This Week brief composition, empty state, history, admin generation and schedule."""
from datetime import timedelta
import pytest
from django.utils import timezone
from apps.insights.models import Brief, Signal
from apps.insights import brief as briefs, signals as engine
from backend.tests.test_signals import placed, section, all_sections, economy, TODAY

pytestmark = pytest.mark.django_db


def test_first_brief_is_a_baseline_with_ranked_items_and_fyi_collapsed():
    loc = placed('Cypress Lake')
    all_sections(loc)
    engine.evaluate(loc, today=TODAY)
    b = briefs.generate()
    assert b.kind == 'baseline' and b.title == 'Baseline: current conditions'
    assert b.items[0]['rule_id'] == 'SIG-11' and b.items[0]['flag'] == 'new'
    assert {i['severity'] for i in b.items} == {'High', 'Watch'}
    assert {i['rule_id'] for i in b.fyi} == {'SIG-07', 'SIG-10'}


def test_next_brief_shows_only_new_or_changed_plus_still_active_high(monkeypatch):
    loc = placed()
    all_sections(loc)
    engine.evaluate(loc, today=TODAY)
    first = briefs.generate()
    later = first.generated_at + timedelta(days=7)
    monkeypatch.setattr(timezone, 'now', lambda: later)
    section(loc, 'economy', economy(priv=-0.05))  # same SIG-03 subject, unchanged severity
    engine.evaluate(loc, today=TODAY)
    b = briefs.generate(now=later)
    assert [(i['rule_id'], i['flag']) for i in b.items] == [('SIG-11', 'still_active')]
    assert b.title == '1 item needs attention across 1 property'


def test_empty_state_when_nothing_material():
    loc = placed()
    section(loc, 'economy', economy(priv=0.0, retail=0.0, unemp=0.0, permits=0.0, units=0))
    engine.evaluate(loc, today=TODAY)
    briefs.generate()
    b = briefs.generate()
    assert b.items == [] and b.title == 'No material changes this week'
    with pytest.raises(ValueError):
        b.save()


def test_candidate_signals_are_not_in_the_brief():
    loc = placed(status='candidate')
    all_sections(loc)
    engine.evaluate(loc, today=TODAY)
    assert briefs.generate().items == []


def test_api_latest_history_and_admin_only_generate(client):
    from django.contrib.auth import get_user_model
    from apps.accounts.models import Membership
    member = get_user_model().objects.create_user(username='m@example.org', email='m@example.org')
    Membership.objects.create(email='m@example.org', user=member, role='member')
    admin = get_user_model().objects.create_user(username='a@example.org', email='a@example.org')
    Membership.objects.create(email='a@example.org', user=admin, role='admin')
    client.force_login(member)
    assert client.get('/api/briefs/latest/').json() == {'brief': None, 'history': []}
    assert client.post('/api/briefs/generate/').status_code == 403
    client.force_login(admin)
    created = client.post('/api/briefs/generate/').json()
    assert created['kind'] == 'baseline'
    latest = client.get('/api/briefs/latest/').json()
    assert latest['brief']['id'] == created['id'] and len(latest['history']) == 1
    assert client.get(f"/api/briefs/{created['id']}/").status_code == 200


def test_brief_weekly_is_registered():
    from apps.operations.registry import REGISTRY
    assert 'brief_weekly' in REGISTRY


def test_county_level_signals_are_grouped_across_properties():
    a, b = placed('Westport A', 41.1), placed('Westport B', 41.2)
    for loc in (a, b):
        section(loc, 'economy', economy(priv=0.0, retail=0.0, unemp=1.0, permits=0.0, units=0))
        engine.evaluate(loc, today=TODAY)
    brief = briefs.generate()
    sig05 = [i for i in brief.items if i['rule_id'] == 'SIG-05']
    assert len(sig05) == 1 and {l['name'] for l in sig05[0]['locations']} == {'Westport A', 'Westport B'}
    assert brief.stats['properties_with_items'] == 2


# ---- R2 item 8 ---------------------------------------------------------------------------

def test_resolved_section_and_place_grouping(monkeypatch):
    from backend.tests.test_signals import section
    a, b = placed('Mall A', 41.1), placed('Mall B', 41.2)
    for loc in (a, b):
        section(loc, 'businesses', {'release': '2026-11-18.0', 'changes': {'closures': [{'id': 'p1', 'name': 'Regal',
            'severity': 'Watch', 'distance_mi': 0.4, 'evidence': 'marked permanently closed'}]}})
        engine.evaluate(loc, today=TODAY)
    first = briefs.generate()
    closures = [i for i in first.items if i['rule_id'] == 'SIG-09']
    assert len(closures) == 1 and {l['name'] for l in closures[0]['locations']} == {'Mall A', 'Mall B'}
    later = first.generated_at + timedelta(days=7)
    monkeypatch.setattr(timezone, 'now', lambda: later)
    Signal.objects.filter(rule_id='SIG-09').update(status='resolved', resolved_reason='condition no longer holds',
        last_changed_at=later)
    nxt = briefs.generate(now=later)
    assert len(nxt.resolved) == 1 and nxt.stats['resolved_items'] == 1


def test_county_alerts_do_not_raise_property_attention():
    from backend.tests.test_signals import section, economy
    loc = placed()
    section(loc, 'economy', economy())
    engine.evaluate(loc, today=TODAY)
    assert Signal.objects.filter(rule_id='SIG-05', status='active').exists()
    assert engine.attention(loc.pk) == 'Clear'


def test_unemployment_uses_three_month_average_relative_to_state():
    import json
    from apps.area import economy as econ

    def series(sid, values):  # values newest first, 15 months from 2026-09
        months = [(2026, m) for m in range(9, 0, -1)] + [(2025, m) for m in range(12, 6, -1)]
        return {'seriesID': sid, 'data': [{'year': str(y), 'period': f'M{m:02d}', 'value': str(v), 'footnotes': [{}]}
            for (y, m), v in zip(months, values)]}
    county = [5.0, 5.0, 5.0] + [4.0] * 9 + [3.5, 3.5, 3.5]
    state = [4.5, 4.5, 4.5] + [4.0] * 9 + [3.5, 3.5, 3.5]
    raw = json.dumps({'status': 'REQUEST_SUCCEEDED', 'Results': {'series': [
        series('LAUCN091900000000003', county), series('LASST090000000000003', state)]}}).encode()
    out = econ.parse_laus(raw, '09190')
    assert out['avg3_change_pts'] == 1.5 and out['state_avg3_change_pts'] == 1.0 and out['excess_vs_state_pts'] == 0.5
    from backend.tests.test_signals import section, economy
    loc = placed()
    e = economy()
    e['unemployment'] = out
    section(loc, 'economy', e)
    engine.evaluate(loc, today=TODAY)
    s = Signal.objects.get(rule_id='SIG-05')
    assert '3-month average' in s.title and s.evidence['more_than_state_pts'] == 0.5
    e['unemployment'] = {**out, 'excess_vs_state_pts': 0.2}  # statewide swing: no alert
    section(loc, 'economy', e)
    engine.evaluate(loc, today=TODAY)
    assert Signal.objects.get(rule_id='SIG-05').status == 'resolved'
