"""Redesign B6b: KPI cards (rank, change, US index) and fixed-template takeaways."""
import pytest
from apps.insights import kpis as k
from apps.insights.metrics import refresh_snapshot
from backend.tests.test_signals import placed, section

pytestmark = pytest.mark.django_db


def portfolio(n=6):
    out = []
    for i in range(n):
        loc = placed(f'P{i}', 41.0 + i / 10)
        section(loc, 'traffic', {'roads': [{'label': f'Route {i}', 'aadt': 10_000 * (i + 1), 'year': 2025,
            'prior_aadt': 10_000 * (i + 1) / 0.9, 'prior_year': 2024, 'change_pct': -0.1 if i == 0 else None,
            'reason': None if i == 0 else 'SAME_COUNT'}]})
        section(loc, 'businesses', {'release': '2026-11-18.0', 'retail_and_services_total': {'1mi': 100 * (i + 1)},
            'nearest_supermarket': {'name': 'Publix Super Market', 'brand': 'Publix', 'distance_mi': 0.5 + i}, 'changes': {}})
        refresh_snapshot(loc)
        out.append(loc)
    return out


def test_cards_rank_against_the_rest_of_the_portfolio():
    locs = portfolio()
    cards = {c['key']: c for c in k.kpis(locs[5])}
    assert [c['key'] for c in k.kpis(locs[5])] == [key for key, *_ in k.KPI_ORDER] + ['flood']
    assert cards['aadt']['value'] == 60_000 and (cards['aadt']['rank'], cards['aadt']['of']) == (1, 6)
    assert cards['aadt']['note'] == 'Estimate carried forward (no newer count)' and cards['aadt']['change'] is None
    assert cards['retail_services_1mi']['rank'] == 1
    # Closer is better for the supermarket: the farthest ranks last.
    assert cards['nearest_supermarket_mi']['rank'] == 6 and cards['nearest_supermarket_mi']['detail'] == 'Publix'
    assert cards['population']['value'] is None and cards['population']['rank'] is None  # no demographics yet
    assert cards['flood']['value'] is None  # hazards not computed: unknown
    first = {c['key']: c for c in k.kpis(locs[0])}
    assert first['aadt']['change'] == {'value': -0.1, 'unit': 'pct', 'since': '2024', 'significant': None}


def test_too_small_a_portfolio_is_not_ranked():
    locs = portfolio(3)
    assert all(c['rank'] is None for c in k.kpis(locs[0]))


def test_takeaways_are_limited_sourced_and_ordered_by_strength():
    locs = portfolio()
    section(locs[0], 'hazards', {'flood_at_pin': {'zone': 'AE', 'sfha': True, 'in_sfha': True, 'bfe_ft': 9.0},
        'flood_nearby': {}, 'nri': {}})
    out = k.takeaways(locs[0])
    assert 1 <= len(out) <= 5 and all(t['source'] and t['tone'] in ('positive', 'neutral', 'caution') for t in out)
    # A standing flood risk outranks a 10% traffic dip.
    assert out[0]['text'].startswith('Inside FEMA high-risk flood zone AE') and out[0]['section'] == 'risk'
    texts = [t['text'] for t in out]
    assert texts[1] == 'Retail and services within 1 mi: 100 — 6th of 6 properties'  # bottom of the portfolio
    assert 'Main road Route 0 carries 10,000 vehicles/day (2025), −10.0% vs the prior count' in texts
    assert [t['tone'] for t in out][:2] == ['caution', 'caution']


def test_us_index_and_ordinals():
    assert k.us_index(114_316, 81_202) == 141 and k.us_index(None, 1) is None and k.us_index(5, 0) is None
    assert [k.ordinal(n) for n in (1, 2, 3, 4, 11, 12, 13, 21, 22, 101)] == \
        ['1st', '2nd', '3rd', '4th', '11th', '12th', '13th', '21st', '22nd', '101st']


def test_reference_rows_from_national_files(tmp_path):
    from apps.demographics import acs
    header = 'GEO_ID|B01003_E001|B01003_M001\n'
    files = {t: [f'GEO_ID|' + '|'.join(f'{t}_{kk}{c}' for c in cells for kk in 'EM') + '\n',
        '0100000US|' + '|'.join('10' for _ in cells for _k in 'EM') + '\n',
        '0400000US09|' + '|'.join('5' for _ in cells for _k in 'EM') + '\n',
        '1500000US091900435001|' + '|'.join('1' for _ in cells for _k in 'EM') + '\n'] for t, cells in acs.TABLES.items()}
    ex = acs.extract_reference(2024, lambda t: iter(files[t]))
    assert set(ex.rows) == {'US', '09'} and ex.rows['US']['B01003_001_E'] == 10
    assert header  # the real file layout: GEO_ID then E/M pairs
