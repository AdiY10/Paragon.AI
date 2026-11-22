"""Redesign B8: ACS depth tables (age, tenure, home value, rent), v2 storage, LODES sectors and earnings."""
import io
import json
from pathlib import Path
import pytest
from apps.demographics import acs
from apps.demographics.metrics import ring_metrics
from apps.demographics.rings import interpolated_median, HOME_VALUE_LOWER_BOUNDS, GROSS_RENT_LOWER_BOUNDS

FIX = Path('tests/fixtures/real/ring_demographics')
BG = '091900435001'


def lines(table):
    return open(FIX / f'acsdt5y2024-{table.lower()}.sample.dat')


@pytest.fixture(scope='module')
def extract():
    return acs.extract_states(2024, ['09'], line_source=lines)[0]


def test_depth_metrics_from_real_block_group(extract):
    row = extract.rows[BG]
    assert row['B25003_001_E'] == 470 and row['B25003_002_E'] == 388  # real values (ACS 2020-2024)
    m = ring_metrics({BG: 1.0}, {BG: row})
    assert m['owner_occupied_share']['value'] == pytest.approx(388 / 470, abs=1e-4)
    shares = sum(m[k]['value'] for k in ('age_under_18_share', 'age_18_34_share', 'age_35_54_share',
        'age_55_64_share', 'age_65_plus_share'))
    assert shares == pytest.approx(1.0, abs=1e-3)
    assert 20 < m['median_age']['value'] < 70
    assert m['median_home_value']['unit'] == 'usd' and (m['median_home_value']['value'] or 0) > 50_000
    assert 0 <= m['households_100k_plus_share']['value'] <= 1


def test_legacy_rows_have_no_depth_metrics_but_keep_income_share():
    row = {f'B19001_{i:03d}_{k}': 10.0 for i in range(1, 18) for k in 'EM'}
    row.update({'B19001_001_E': 160.0, 'B01003_001_E': 400.0, 'B01003_001_M': 5.0, 'B11001_001_E': 160.0,
        'B11001_001_M': 3.0, 'B15003_001_E': 1.0, 'B15003_001_M': 0.0, 'B19025_001_E': 1.0, 'B19025_001_M': 0.0,
        **{f'B15003_{c}_{k}': 0.0 for c in ('022', '023', '024', '025') for k in 'EM'}})
    m = ring_metrics({'x': 1.0}, {'x': row})
    assert 'median_age' not in m and 'owner_occupied_share' not in m
    assert m['households_100k_plus_share']['value'] == pytest.approx(40 / 160)


def test_open_ended_medians_say_so():
    counts = [0] * 25 + [10]
    assert interpolated_median(counts, HOME_VALUE_LOWER_BOUNDS) == (2_000_000.0, True)
    rent = [0] * 18 + [10] + [0] * 5
    value, open_ended = interpolated_median(rent, GROSS_RENT_LOWER_BOUNDS)
    assert 1_250 <= value <= 1_500 and not open_ended


@pytest.mark.django_db
def test_v2_snapshots_round_trip_and_load_only_the_rings_block_groups(extract, tmp_path):
    from apps.sources.catalog import sync_catalog
    from apps.sources.storage import LocalArtifactStore
    sync_catalog()
    store = LocalArtifactStore(tmp_path)
    snap, _ = acs.publish_extract(extract, store)
    assert snap.adapter_version == 'acs-table-sf-v2' and snap.context['format'] == 'jsonl.gz'
    every = acs.load_rows(snap, store)
    assert set(every) == set(extract.rows) and every[BG] == extract.rows[BG]
    assert set(acs.load_rows(snap, store, geoids={BG, '999999999999'})) == {BG}


@pytest.mark.django_db
def test_outdated_snapshots_are_re_ingested(extract, tmp_path):
    from apps.sources.catalog import sync_catalog
    from apps.sources.storage import LocalArtifactStore
    from apps.demographics import service
    from apps.sources.models import SourceSnapshot
    sync_catalog()
    snap, _ = acs.publish_extract(extract, LocalArtifactStore(tmp_path))
    assert service.current_states(2024) == {'09'}
    SourceSnapshot._base_manager.filter(pk=snap.pk).update(adapter_version='acs-table-sf-v1')  # an old v1 copy
    assert service.current_states(2024) == set() and service.ingested_states(2024) == {'09'}


def test_lodes_sectors_and_earnings_add_up():
    from apps.area import jobs as lodes
    wac = lodes.parse_wac(Path('tests/fixtures/real/area/ct_wac_S000_JT00_2024.norwalk5mi.csv.gz').read_bytes())
    from backend.tests.test_area_profile import norwalk_blocks
    blocks = norwalk_blocks()
    rings = lodes.ring_jobs(blocks, wac, (41.126611, -73.388299), (1, 3))
    for r in rings.values():
        assert sum(r['sectors'].values()) == r['total'] and sum(r['earnings'].values()) == r['total']
        assert r['sectors']['retail'] == r['retail'] and min(r['sectors'].values()) >= 0
    assert rings[3]['total'] == 45424  # unchanged headline (verified 2026-11-19)
