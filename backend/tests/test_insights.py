"""T3: portfolio percentiles (MET-20) and evidence summary (FR-26)."""
import pytest
from apps.insights import metrics as m

pytestmark = pytest.mark.django_db


def test_percentile_counts_ties_half():
    assert m.percentile(5, [1, 2, 3, 4, 6, 7, 8, 9]) == 50
    assert m.percentile(10, [1, 2, 3, 4, 5]) == 100
    assert m.percentile(3, [3, 3, 1, 5]) == 50


def make_owned(n):
    from apps.locations.service import create_location, change_pin
    out = []
    for i in range(n):
        loc = create_location(name=f'Center {i}', address=f'{i} Main St', actor=None)
        loc.status = 'owned'
        loc.save()
        out.append(change_pin(location_id=loc.pk, expected_version=loc.version, lat=41 + i / 100, lon=-73, actor=None))
    return out


def fake_extract(table):
    def extract(location, fresh=False):
        return dict(table.get(location.name, {}))
    return extract


def test_summary_strengths_concerns_and_direction(monkeypatch):
    locs = make_owned(7)
    table = {f'Center {i}': {'population': {'value': 10000 * (i + 1), 'period': 'ACS 2020–2024 5-year', 'source': 'SRC-03'},
        'unemployment_change': {'value': 0.1 * i, 'period': '2026-09', 'source': 'SRC-07'}} for i in range(6)}
    table['Center 6'] = {'population': {'value': 999999, 'period': 'ACS', 'source': 'SRC-03'},
        'unemployment_change': {'value': 5.0, 'period': '2026-09', 'source': 'SRC-07'},
        '_hazards': {'concerns': ['Pin is in FEMA zone AE (Special Flood Hazard Area)']}}
    monkeypatch.setattr(m, 'extract', fake_extract(table))
    out = m.summary(locs[6])
    assert out['benchmark_ready'] and out['portfolio_size'] == 6
    pop = next(x for x in out['metrics'] if x['key'] == 'population')
    assert pop['percentile'] == 100 and pop['n'] == 6
    assert out['strengths'][0]['text'].startswith('Population within 3 miles: 999,999, better than 100%')
    # Rising unemployment is a concern (lower is better), hazards rank first.
    assert out['concerns'][0]['text'].startswith('Pin is in FEMA zone AE')
    assert any(c['metric'] == 'unemployment_change' for c in out['concerns'])


def test_small_portfolio_has_no_percentiles(monkeypatch):
    locs = make_owned(4)
    table = {l.name: {'population': {'value': 1000 * i, 'period': 'p', 'source': 'SRC-03'}} for i, l in enumerate(locs)}
    monkeypatch.setattr(m, 'extract', fake_extract(table))
    out = m.summary(locs[0])
    assert out['benchmark_ready'] is False and out['strengths'] == [] and out['concerns'] == []
    assert all(x['percentile'] is None for x in out['metrics'])


def test_signals_rank_above_other_concerns(monkeypatch):
    locs = make_owned(1)
    monkeypatch.setattr(m, 'extract', fake_extract({}))
    out = m.summary(locs[0], signals=[{'title': 'Tenant bankruptcy filing', 'severity': 'High', 'source': 'SRC-14'},
        {'title': 'Minor note', 'severity': 'FYI'}])
    assert [c['text'] for c in out['concerns']] == ['Tenant bankruptcy filing (High)']


def test_extract_reads_real_stored_sections(tmp_path, client, settings):
    from backend.tests.test_area_profile import setup, FixtureOpener, KINGSTON
    from apps.area.service import compute_area
    location = setup(tmp_path, client, *KINGSTON, settings)
    compute_area(location.pk, sections=('economy', 'traffic', 'hazards'), opener=FixtureOpener('kingston'))
    location.refresh_from_db()
    values = m.extract(location)
    assert values['aadt']['value'] == 22422 and values['aadt']['detail'] == 'Ulster Ave US 9W'
    assert values['private_jobs_yoy']['value'] == pytest.approx(0.048)
    assert values['permits_change']['value'] == pytest.approx((739 - 421) / 421)
    body = client.get(f'/api/locations/{location.pk}/summary/').json()
    assert body['benchmark_ready'] is False and any(x['key'] == 'aadt' and x['value'] == 22422 for x in body['metrics'])


def test_every_rendered_number_has_source_and_period(tmp_path, client, settings):
    """AC-25: no value without provenance, from real stored sections."""
    from backend.tests.test_area_profile import setup, FixtureOpener, KINGSTON
    from apps.area.service import compute_area
    location = setup(tmp_path, client, *KINGSTON, settings)
    compute_area(location.pk, sections=('economy', 'traffic', 'hazards'), opener=FixtureOpener('kingston'))
    location.refresh_from_db()
    body = client.get(f'/api/locations/{location.pk}/summary/').json()
    shown = [m for m in body['metrics'] if m['value'] is not None]
    assert shown and all(m['source'] and m['period'] for m in shown)
    area = client.get(f'/api/locations/{location.pk}/area/').json()['sections']
    for name, sec in area.items():
        if sec['status'] in ('available', 'unavailable') and sec.get('sources'):
            assert all(s['id'] and s['period'] and s['retrieved_at'] and s['url'].startswith('https://') for s in sec['sources'])


# ---- R2 item 13: query budgets -------------------------------------------------------------

def test_query_budgets_do_not_grow_with_the_portfolio(client):
    from django.db import connection
    from django.test.utils import CaptureQueriesContext
    from backend.tests.test_accounts import member
    from backend.tests.test_signals import section, economy
    locs = make_owned(12)
    for loc in locs:
        section(loc, 'economy', economy())
    user, _ = member()
    client.force_login(user)
    ids = ','.join(str(l.pk) for l in locs[:3])
    urls = ['/api/locations/?page_size=200', f'/api/locations/{locs[0].pk}/summary/', f'/api/compare/?ids={ids}']
    for url in urls:
        client.get(url)  # warm the snapshots
    budgets = {}
    for url in urls:
        with CaptureQueriesContext(connection) as q:
            assert client.get(url).status_code == 200
        budgets[url] = len(q.captured_queries)
    assert budgets[urls[0]] <= 12 and budgets[urls[1]] <= 20 and budgets[urls[2]] <= 22, budgets


def test_snapshot_follows_reviews_and_pin_moves(client):
    from apps.insights.models import LocationMetrics, Signal
    from apps.insights.signals import safe_evaluate, cached_attention
    from backend.tests.test_signals import section, all_sections
    loc = make_owned(1)[0]
    all_sections(loc)
    safe_evaluate(loc.pk)
    loc.refresh_from_db()
    assert LocationMetrics.objects.get(location=loc).attention == 'Watch' and cached_attention(loc) == 'Watch'
    from apps.locations.service import change_pin
    loc = change_pin(location_id=loc.pk, expected_version=loc.version, lat=41.5, lon=-73, actor=None)
    assert cached_attention(loc) in ('High', 'Watch', 'Clear')  # stale row ignored, recomputed live


def test_location_list_carries_key_numbers_and_unconfirmed_tenants(client):
    import uuid
    from backend.tests.test_accounts import member
    from apps.insights.metrics import refresh_snapshot
    from apps.locations import tenants as svc
    loc = make_owned(1)[0]
    user, _ = member()
    client.force_login(user)
    svc.create_tenant(location_id=loc.pk, name='Stop & Shop', request_key=uuid.uuid4(), actor=user)
    from apps.insights import metrics as mm
    import unittest.mock as um
    with um.patch.object(mm, 'extract', lambda location, fresh=False: {'population': {'value': 41000}, 'aadt': {'value': 18000}}):
        refresh_snapshot(loc)
    row = next(r for r in client.get('/api/locations/').json()['results'] if r['id'] == str(loc.pk))
    assert row['key_numbers'] == {'population': 41000, 'aadt': 18000, 'flood': None, 'nearest_supermarket': None,
        'active_alerts': 0} and row['unconfirmed_tenants'] == 1
