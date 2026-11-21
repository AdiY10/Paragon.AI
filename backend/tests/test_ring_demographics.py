"""Ring demographics: math, parsers, real-data reference values and service behaviour."""
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import pytest
from apps.demographics import acs, geography
from apps.demographics.rings import (Block, BlockGroupTotals, Estimate, ring_weights, weighted_sum,
    ratio, proportion, interpolated_median, reliability, haversine_miles)
from apps.demographics.metrics import compute_rings, ring_metrics

FIX = Path('tests/fixtures/real/ring_demographics')
NORWALK = (41.126611, -73.388299)   # 444 Westport Ave (Staples Plaza), docs/03 V1


def lines(table):
    return open(FIX / f'acsdt5y2024-{table.lower()}.sample.dat')


# ---- pure math -------------------------------------------------------------

def test_haversine_one_degree_latitude():
    assert haversine_miles(41, -73, 42, -73) == pytest.approx(69.09, abs=0.05)


def _blocks():
    # Two block groups; BG A has 3 blocks (2 inside 1 mi), BG B one block outside, BG C empty.
    return [Block('090010001001001', 100, 1000, 41.0, -73.0),
            Block('090010001001002', 300, 1000, 41.005, -73.0),
            Block('090010001001003', 600, 1000, 41.2, -73.0),
            Block('090010001002001', 50, 500, 41.3, -73.0),
            Block('090010001003001', 0, 400, 41.001, -73.0),
            Block('090010001003002', 0, 600, 41.4, -73.0)]


def test_population_weights_use_blocks_inside_ring_and_area_fallback():
    totals = {'090010001001': BlockGroupTotals(1000, 3000), '090010001002': BlockGroupTotals(50, 500),
        '090010001003': BlockGroupTotals(0, 1000)}
    w = ring_weights((41.0, -73.0), 1, _blocks(), totals)
    assert w.weights['090010001001'] == pytest.approx(0.4)
    assert '090010001002' not in w.weights
    assert w.weights['090010001003'] == pytest.approx(0.4) and w.methods['090010001003'] == 'land_area'
    assert w.blocks_inside == 3


def test_missing_block_group_totals_fail_closed():
    with pytest.raises(ValueError):
        ring_weights((41.0, -73.0), 1, _blocks(), {})


@pytest.mark.parametrize('radius', [0, -1, 26, float('nan')])
def test_invalid_radius_rejected(radius):
    with pytest.raises(ValueError):
        ring_weights((41.0, -73.0), radius, _blocks(), {})


def test_weighted_sum_and_moe_root_sum_of_squares():
    rows = {'a': {'X_E': 100.0, 'X_M': 30.0}, 'b': {'X_E': 200.0, 'X_M': 40.0}}
    est = weighted_sum({'a': 1.0, 'b': 0.5}, rows, 'X')
    assert est.value == pytest.approx(200) and est.moe == pytest.approx(math.sqrt(30**2 + 20**2))


def test_weighted_sum_never_invents_missing_values():
    assert weighted_sum({'a': 1.0}, {'a': {'X_E': None, 'X_M': None}}, 'X').reason == 'SUPPRESSED'
    assert weighted_sum({'z': 1.0}, {}, 'X').reason == 'NOT_COVERED'
    unknown_moe = weighted_sum({'a': 1.0}, {'a': {'X_E': 5.0, 'X_M': None}}, 'X')
    assert unknown_moe.value == 5 and unknown_moe.moe is None


def test_ratio_and_proportion_census_formulas():
    r = ratio(Estimate(1000, 100), Estimate(10, 2))
    assert r.value == 100 and r.moe == pytest.approx(math.sqrt(100**2 + 100**2 * 2**2) / 10)
    p = proportion(Estimate(50, 10), Estimate(100, 5))
    assert p.value == 0.5 and p.moe == pytest.approx(math.sqrt(10**2 - 0.25 * 5**2) / 100)
    # Negative radicand falls back to the ratio formula.
    q = proportion(Estimate(90, 1), Estimate(100, 20))
    assert q.moe == pytest.approx(math.sqrt(1 + 0.81 * 400) / 100)
    assert ratio(Estimate(1, 1), Estimate(0, 0)).reason == 'NOT_ENOUGH_DATA'


def test_interpolated_median_and_open_ended_top_bracket():
    counts = [0] * 16
    counts[11] = 10   # all in 75k-100k
    assert interpolated_median(counts) == (87_500, False)
    top = [0] * 16
    top[15] = 5
    assert interpolated_median(top) == (200_000, True)
    assert interpolated_median([0] * 16) == (None, False)


@pytest.mark.parametrize('moe,expected', [(10, 'high'), (40, 'medium'), (60, 'low'), (90, 'very_low')])
def test_reliability_classes(moe, expected):
    # CV = (MOE / 1.645) / estimate: 0.06, 0.24, 0.36, 0.55
    assert reliability(Estimate(100, moe)) == expected
    assert reliability(Estimate(100, None)) is None


# ---- ACS parsing (real table slices) ----------------------------------------

def test_real_acs_slices_parse_block_groups_only_with_jam_values():
    ex = acs.extract_states(2024, ['09'], line_source=lines)[0]
    assert set(ex.rows) == {'091900435001', '091900435002', '091104173001'}
    assert ex.rows['091900435001']['B01003_001_E'] == 1103 and ex.rows['091900435001']['B01003_001_M'] == 172
    assert ex.rows['091900435001']['B19025_001_E'] == 68_595_100
    # Census omits B19025 for this tiny block group: absent means "not published", never zero.
    assert ex.rows['091104173001']['B19025_001_E'] is None


def test_acs_jam_values():
    assert acs.parse_value('-666666666') is None
    assert acs.parse_value('-555555555', moe=True) == 0.0
    assert acs.parse_value('-222222222', moe=True) is None
    with pytest.raises(acs.AcsError):
        acs.parse_value('abc')


def test_acs_rejects_bad_headers_and_old_vintages():
    with pytest.raises(acs.AcsError):
        list(acs.parse_table(iter(['NOPE|x\n']), 'B01003', ['09']))
    with pytest.raises(acs.AcsError):
        list(acs.parse_table(iter(['GEO_ID|B01003_E001\n']), 'B01003', ['09']))
    with pytest.raises(acs.AcsError):
        acs.extract_states(2019, ['09'], line_source=lines)
    with pytest.raises(acs.AcsError):
        acs.extract_states(2024, ['9'], line_source=lines)


# ---- real-data reference values (docs/03 V5, V6; AC-06) -----------------------

@pytest.fixture(scope='module')
def norwalk():
    capture = geography.GeographyCapture.from_payload(
        (FIX / 'norwalk_444_westport_5mi.geography.json').read_bytes(), datetime.now(timezone.utc))
    rows = json.loads((FIX / 'norwalk_acs2024_rows.json').read_text())['rows']
    blocks, totals, mapping, unresolved = geography.parse_geography(capture)
    return compute_rings(NORWALK, (1, 3, 5), blocks, totals, mapping, unresolved, rows), mapping, unresolved


def test_connecticut_planning_region_mapping(norwalk):
    _, mapping, unresolved = norwalk
    assert mapping['090010435001'] == '091900435001'
    assert unresolved == {'090019900000'}   # zero-population water block group only


def test_norwalk_ring_population_matches_reference_values(norwalk):
    rings, *_ = norwalk
    pop = {r['radius_miles']: r['metrics']['population'] for r in rings}
    # Paragon's listing (Esri 2021): 11,474 / 84,256 / 132,645. Tolerance ±10% (AC-06).
    assert pop[1]['value'] == pytest.approx(11_500, rel=0.10)
    assert pop[3]['value'] == pytest.approx(84_000, rel=0.10)
    assert pop[5]['value'] == pytest.approx(132_645, rel=0.10)
    for p in pop.values():
        assert p['moe'] > 0 and p['reliability'] == 'high' and p['metric_id'] == 'MET-01'


def test_norwalk_metrics_are_complete_and_plausible(norwalk):
    rings, *_ = norwalk
    three = next(r for r in rings if r['radius_miles'] == 3)
    m = three['metrics']
    assert 25_000 < m['households']['value'] < 45_000
    assert 50_000 < m['median_household_income']['value'] < 250_000
    assert m['mean_household_income']['value'] > m['median_household_income']['value']
    assert m['mean_household_income']['household_coverage'] >= 0.95
    assert 0.2 < m['bachelors_or_higher_share']['value'] < 0.8
    assert three['method']['block_groups'] > 50


def test_unresolved_weighted_block_group_withholds_ring(norwalk):
    capture = geography.GeographyCapture.from_payload(
        (FIX / 'norwalk_444_westport_5mi.geography.json').read_bytes(), datetime.now(timezone.utc))
    rows = json.loads((FIX / 'norwalk_acs2024_rows.json').read_text())['rows']
    blocks, totals, mapping, unresolved = geography.parse_geography(capture)
    unresolved = set(unresolved) | {'090010435001'}
    mapping = {k: v for k, v in mapping.items() if k != '090010435001'}
    ring = compute_rings(NORWALK, (1,), blocks, totals, mapping, unresolved, rows)[0]
    assert ring['metrics']['population']['value'] is None
    assert ring['metrics']['population']['reason'] == 'GEOGRAPHY_CHANGED'


def test_mean_income_withheld_when_coverage_low():
    rows = {'a': {'B11001_001_E': 100.0, 'B11001_001_M': 5.0, 'B19025_001_E': None, 'B19025_001_M': None},
            'b': {'B11001_001_E': 10.0, 'B11001_001_M': 2.0, 'B19025_001_E': 1e6, 'B19025_001_M': 1e5}}
    for g in rows:
        rows[g].update({'B01003_001_E': 1.0, 'B01003_001_M': 1.0, 'B15003_001_E': 1.0, 'B15003_001_M': 1.0,
            **{f'B15003_{c}_{k}': 0.0 for c in ('022', '023', '024', '025') for k in 'EM'},
            **{f'B19001_{i:03d}_{k}': 1.0 for i in range(2, 18) for k in 'EM'}})
    m = ring_metrics({'a': 1.0, 'b': 1.0}, rows)['mean_household_income']
    assert m['value'] is None and m['reason'] == 'SUPPRESSED' and m['household_coverage'] < 0.95


def test_geography_parser_rejects_malformed_blocks():
    bad = geography.GeographyCapture(41, -73, 1, 2024, [{'GEOID': '123'}], [], [], datetime.now(timezone.utc))
    with pytest.raises(geography.GeographyError):
        geography.parse_geography(bad)
    missing_totals = geography.GeographyCapture(41, -73, 1, 2024,
        [{'GEOID': '090010001001001', 'POP100': 1, 'AREALAND': 1, 'INTPTLAT': 41, 'INTPTLON': -73}], [], [],
        datetime.now(timezone.utc))
    with pytest.raises(geography.GeographyError):
        geography.parse_geography(missing_totals)


# ---- service and API (database) ---------------------------------------------

@pytest.fixture
def placed(tmp_path, client):
    return setup_location(tmp_path, client, with_acs=True)


def setup_location(tmp_path, client, *, with_acs, with_baseline=False):
    from apps.sources.catalog import sync_catalog
    from apps.sources.storage import LocalArtifactStore
    from apps.locations.service import change_pin
    from django.contrib.auth import get_user_model
    from apps.accounts.models import Membership
    sync_catalog()
    user = get_user_model().objects.create_user(username='member@example.org', email='member@example.org')
    Membership.objects.create(email='member@example.org', user=user, role='member')
    client.force_login(user)
    store = LocalArtifactStore(tmp_path / 'artifacts')
    created = client.post('/api/locations/', {'name': 'Staples Plaza', 'address': '444 Westport Avenue, Norwalk, CT'},
        content_type='application/json').json()
    location = change_pin(location_id=created['id'], expected_version=created['version'], lat=NORWALK[0], lon=NORWALK[1],
        actor=user, method='manual')
    capture = geography.GeographyCapture.from_payload(
        (FIX / 'norwalk_444_westport_5mi.geography.json').read_bytes(), datetime(2026, 11, 19, tzinfo=timezone.utc))
    geography.publish_capture(capture, store)
    rows = json.loads((FIX / 'norwalk_acs2024_rows.json').read_text())['rows']
    if with_baseline:
        from apps.demographics import cpi
        base_capture = geography.GeographyCapture.from_payload(
            (FIX / 'norwalk_444_westport_5mi.geography2010.json').read_bytes(), datetime(2026, 11, 19, tzinfo=timezone.utc))
        geography.publish_capture(base_capture, store)
        legacy = legacy_extract()
        acs.publish_extract(acs.AcsExtract(2019, '09', legacy.rows, (acs.LEGACY_BASE + 'Connecticut_Tracts_Block_Groups_Only.zip',),
            datetime(2026, 11, 19, tzinfo=timezone.utc)), store)
        values = cpi.parse((FIX / 'bls_cpi_u_2019_2024.json').read_bytes(), (2019, 2024))
        cpi.publish(values, datetime(2026, 11, 19, tzinfo=timezone.utc), store)
    if with_acs:
      acs.publish_extract(acs.AcsExtract(2024, '09', rows, (acs.BASE_URL.format(year=2024, table='b01003'),),
        datetime(2026, 11, 19, tzinfo=timezone.utc)), store)
    return location, store, user


@pytest.mark.django_db
def test_compute_stores_immutable_result_and_api_serves_it(placed, client):
    from apps.demographics.service import compute_for_location
    location, store, _ = placed
    url = f'/api/locations/{location.pk}/demographics/'
    assert client.get(url).json()['reason'] == 'NOT_COMPUTED'
    result = compute_for_location(location.pk, store=store)
    again = compute_for_location(location.pk, store=store)
    assert again.pk == result.pk
    with pytest.raises(ValueError):
        result.save()
    body = client.get(url).json()
    assert body['status'] == 'available' and body['data_period'] == 'ACS 2020–2024 5-year'
    assert [r['radius_miles'] for r in body['rings']] == [1, 3, 5]
    assert {s['id'] for s in body['sources']} == {'SRC-03', 'SRC-04'}


@pytest.mark.django_db
def test_moving_pin_makes_result_stale_not_wrong(placed, client):
    from apps.demographics.service import compute_for_location
    from apps.locations.service import change_pin
    location, store, user = placed
    compute_for_location(location.pk, store=store)
    location.refresh_from_db()
    change_pin(location_id=location.pk, expected_version=location.version, lat=41.13, lon=-73.39, actor=user)
    body = client.get(f'/api/locations/{location.pk}/demographics/').json()
    assert body['status'] == 'unavailable' and body['reason'] == 'STALE'


class Offline:
    def open(self, *args, **kwargs):
        raise OSError('network disabled in tests')


@pytest.mark.django_db
def test_missing_acs_state_is_reported_not_guessed(tmp_path, client):
    from apps.demographics.service import compute_for_location, DemographicsUnavailable
    from apps.demographics.models import RingDemographics
    location, store, _ = setup_location(tmp_path, client, with_acs=False)
    with pytest.raises(DemographicsUnavailable) as exc:
        compute_for_location(location.pk, store=store, opener=Offline())
    assert exc.value.code == 'NOT_COVERED' and 'state 09' in exc.value.message
    assert not RingDemographics.objects.exists()


@pytest.mark.django_db
def test_source_outage_is_reported_not_guessed(placed):
    from apps.demographics.service import compute_for_location, DemographicsUnavailable
    from apps.sources.models import SourceSnapshot
    location, store, _ = placed
    with pytest.raises(DemographicsUnavailable) as exc:
        compute_for_location(location.pk, store=store, year=2021, opener=Offline())  # 2021 has its own geography
    assert exc.value.code == 'SOURCE_ERROR'
    assert not SourceSnapshot.objects.filter(source_id='SRC-03', release='2021').exists()


@pytest.mark.django_db
def test_unplaced_and_anonymous_requests(client, placed):
    location, *_ = placed
    client.logout()
    assert client.get(f'/api/locations/{location.pk}/demographics/').status_code == 403


# ---- 2015-2019 baseline and trends -------------------------------------------

LEGACY = FIX / 'acs2019_ct'


def legacy_extract():
    geo = (LEGACY / 'g20195ct.csv').read_text(encoding='latin-1')
    seqs = {seq: tuple((LEGACY / f'{k}20195ct{seq}000.txt').read_text(encoding='latin-1') for k in 'em')
        for seq in {v[0] for v in acs.LEGACY_LAYOUT.values()}}
    return acs.parse_legacy('09', geo, seqs)


def test_legacy_layout_matches_official_lookup():
    acs.check_legacy_layout(open(FIX / 'ACS_5yr_Seq_Table_Number_Lookup.2019.slice.txt', encoding='latin-1'))
    import copy
    saved = copy.deepcopy(acs.LEGACY_LAYOUT)
    try:
        acs.LEGACY_LAYOUT['B19025'] = ('0058', 196, 1)
        with pytest.raises(acs.AcsError):
            acs.check_legacy_layout(open(FIX / 'ACS_5yr_Seq_Table_Number_Lookup.2019.slice.txt', encoding='latin-1'))
    finally:
        acs.LEGACY_LAYOUT.clear(); acs.LEGACY_LAYOUT.update(saved)


def test_legacy_sequence_files_parse_real_connecticut_block_groups():
    ex = legacy_extract()
    row = ex.rows['090010435001']
    assert ex.year == 2019 and len(ex.rows) == 124
    assert (row['B01003_001_E'], row['B01003_001_M']) == (645, 159)
    assert row['B11001_001_E'] == 286 and row['B19025_001_E'] == 27_918_400
    assert all(k in row for k in ('B19001_017_E', 'B15003_025_M'))


def test_legacy_parser_rejects_malformed_sequences():
    geo = (LEGACY / 'g20195ct.csv').read_text(encoding='latin-1')
    seqs = {seq: ('ACSSF,2019e5,ct,000,9999,0000001,1', '') for seq in {v[0] for v in acs.LEGACY_LAYOUT.values()}}
    with pytest.raises(acs.AcsError):
        acs.parse_legacy('09', geo, seqs)
    with pytest.raises(acs.AcsError):
        acs.parse_legacy('09', 'ACSSF,CT,040,00,0000001', {})


def test_cpi_parses_real_bls_annual_averages():
    from apps.demographics import cpi
    values = cpi.parse((FIX / 'bls_cpi_u_2019_2024.json').read_bytes(), (2019, 2024))
    assert values == {'2019': 255.657, '2024': 313.689}
    with pytest.raises(cpi.CpiError):
        cpi.parse((FIX / 'bls_cpi_u_2019_2024.json').read_bytes(), (2018, 2024))


def test_trend_significance_scaling_and_guards():
    from apps.demographics.trends import trend
    cur = {'value': 110.0, 'moe': 5.0, 'reliability': 'high'}
    base = {'value': 100.0, 'moe': 5.0, 'reliability': 'high'}
    t = trend('MET-06', cur, base, period='p')
    assert t['value'] == pytest.approx(0.10) and t['difference_moe'] == pytest.approx(math.sqrt(50), abs=1e-3)
    assert t['z'] == pytest.approx(10 / (math.sqrt(50) / 1.645), abs=1e-3) and t['significant'] is True
    scaled = trend('MET-07', cur, base, scale=1.1, period='p')
    assert scaled['value'] == pytest.approx(0) and scaled['significant'] is False
    assert trend('MET-06', {**cur, 'reliability': 'very_low'}, base, period='p')['significant'] is False
    assert trend('MET-06', {**cur, 'moe': None}, base, period='p')['significant'] is None
    assert trend('MET-06', cur, {'value': 0, 'moe': 1}, period='p')['reason'] == 'NOT_ENOUGH_DATA'
    assert trend('MET-06', {'value': None, 'reason': 'SUPPRESSED'}, base, period='p')['reason'] == 'SUPPRESSED'


def test_norwalk_real_trend_reference():
    from apps.demographics.trends import ring_trends
    cur_cap = geography.GeographyCapture.from_payload(
        (FIX / 'norwalk_444_westport_5mi.geography.json').read_bytes(), datetime.now(timezone.utc))
    base_cap = geography.GeographyCapture.from_payload(
        (FIX / 'norwalk_444_westport_5mi.geography2010.json').read_bytes(), datetime.now(timezone.utc))
    rows = json.loads((FIX / 'norwalk_acs2024_rows.json').read_text())['rows']
    cur = compute_rings(NORWALK, (1, 3, 5), *geography.parse_geography(cur_cap), rows)
    base = compute_rings(NORWALK, (1, 3, 5), *geography.parse_geography(base_cap), legacy_extract().rows)
    three = ring_trends(cur[1], base[1], 313.689 / 255.657, 'CPI-U')
    # Verified 2026-11-19: 79,937 -> 85,544 (+7.0%, z≈2.04, significant at 90%).
    assert base[1]['metrics']['population']['value'] == pytest.approx(79_937, rel=0.001)
    assert three['population_change']['value'] == pytest.approx(0.070, abs=0.002)
    assert three['population_change']['significant'] is True
    assert three['real_mean_income_change']['significant'] is False


@pytest.mark.django_db
def test_service_stores_trends_with_baseline_provenance(tmp_path, client):
    from apps.demographics.service import compute_for_location
    location, store, _ = setup_location(tmp_path, client, with_acs=True, with_baseline=True)
    result = compute_for_location(location.pk, store=store, opener=Offline())
    assert result.baseline['acs_year'] == 2019 and result.baseline['cpi_ratio'] == pytest.approx(1.22699, abs=1e-4)
    three = result.rings[1]
    assert three['trends']['population_change']['significant'] is True
    assert three['baseline']['acs_period'] == 'ACS 2015–2019 5-year'
    body = client.get(f'/api/locations/{location.pk}/demographics/').json()
    assert body['trend_baseline']['acs_year'] == 2019


@pytest.mark.django_db
def test_missing_baseline_keeps_current_metrics_and_explains_trends(placed):
    from apps.demographics.service import compute_for_location
    location, store, _ = placed
    result = compute_for_location(location.pk, store=store, opener=Offline())
    ring = result.rings[0]
    assert ring['metrics']['population']['value'] > 0
    assert ring['trends']['population_change']['value'] is None
    assert ring['trends']['population_change']['reason'] == 'SOURCE_ERROR'
    assert result.baseline == {}


@pytest.mark.django_db
def test_post_enqueues_one_job_per_analysis_version_and_worker_computes(tmp_path, client, settings):
    from apps.operations.models import JobRun
    from apps.operations.runner import execute_job
    from apps.demographics.models import RingDemographics
    location, store, _ = setup_location(tmp_path, client, with_acs=True, with_baseline=True)
    settings.SOURCE_ARTIFACT_ROOT = tmp_path / 'artifacts'
    url = f'/api/locations/{location.pk}/demographics/'
    first, second = client.post(url), client.post(url)
    assert first.status_code == second.status_code == 202
    assert first.json()['job_id'] == second.json()['job_id'] and second.json()['created'] is False
    job = JobRun.objects.get(kind='compute_ring_demographics')
    assert job.parameters == {'location_id': str(location.pk), 'analysis_version': location.analysis_version}
    execute_job(str(job.pk))
    job.refresh_from_db()
    assert job.status == JobRun.Status.SUCCEEDED and RingDemographics.objects.count() == 1
    assert client.get(url).json()['status'] == 'available'


@pytest.mark.django_db
def test_post_requires_a_placed_pin(client, tmp_path):
    from django.contrib.auth import get_user_model
    from apps.accounts.models import Membership
    user = get_user_model().objects.create_user(username='m@example.org', email='m@example.org')
    Membership.objects.create(email='m@example.org', user=user, role='member')
    client.force_login(user)
    created = client.post('/api/locations/', {'name': 'Unplaced', 'address': '1 Main St, Anytown, CT'},
        content_type='application/json').json()
    assert client.post(f"/api/locations/{created['id']}/demographics/").status_code == 400
    assert client.get(f"/api/locations/{created['id']}/demographics/").json()['reason'] == 'NOT_PROVIDED'


# ---- R2 item 9: ACS vintage rollover ------------------------------------------------------

@pytest.mark.django_db
def test_portfolio_switches_vintage_only_when_every_state_is_in(tmp_path, client, monkeypatch):
    from apps.demographics import vintage
    from apps.demographics.service import compute_for_location, current_result
    from apps.area import refresh
    from apps.locations.models import Location
    location, store, _ = setup_location(tmp_path, client, with_acs=True, with_baseline=True)
    Location.objects.filter(pk=location.pk).update(state='CT', status='owned')
    first = compute_for_location(location.pk, store=store, opener=Offline())
    assert first.acs_year == 2024 and first.rings[1]['trends']['population_change']['period'] == '2015–2019 → 2020–2024'
    needed = vintage.required_states()
    assert '09' in needed
    rows = json.loads((FIX / 'norwalk_acs2024_rows.json').read_text())['rows']

    def publish(year, state):
        acs.publish_extract(acs.AcsExtract(year, state, rows if state == '09' else {},
            (acs.BASE_URL.format(year=year, table='b01003'),), datetime(2026, 11, 20, tzinfo=timezone.utc)), store)
    publish(2025, '09')
    assert vintage.current_acs_year() == 2024  # neighbours not in yet: stay on 2024
    for state in needed - {'09'}:
        publish(2025, state)
        publish(2024, state)
    assert vintage.current_acs_year() == 2025
    # The monthly refresh recomputes anyone not on the current vintage, reusing the 2020-era geography.
    monkeypatch.setattr(refresh, 'newest_acs_year', lambda opener=None: 2025)
    monkeypatch.setattr('apps.demographics.service._store', lambda s: store)
    monkeypatch.setattr('apps.demographics.service.ingest_acs', lambda *a, **k: [])
    monkeypatch.setattr(refresh, '_each', lambda *a, **k: refresh.Outcome())
    from apps.demographics import cpi

    def no_network(*a, **k):
        raise cpi.CpiError('offline')
    monkeypatch.setattr(cpi, 'fetch', no_network)
    out = refresh.refresh_annual(type('C', (), {'heartbeat': lambda self: None})(), acs_opener=Offline())
    assert out.done == 1 and out.info['acs_year'] == 2025
    now = current_result(location)
    assert now.acs_year == 2025 and now.data_period == 'ACS 2021–2025 5-year'
    assert now.geography_snapshot_id == first.geography_snapshot_id
    # CPI for 2025 is unavailable offline: trends say so rather than mixing vintages.
    assert now.rings[1]['trends']['population_change']['reason'] == 'SOURCE_ERROR'
