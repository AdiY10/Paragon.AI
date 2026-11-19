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
    def extract(location):
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
