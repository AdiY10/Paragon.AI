"""Economy, traffic and hazard sections: parsers on recorded real responses, service, API, job."""
from datetime import date, datetime, timezone
from email.message import Message
import io
import json
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit
import pytest
from apps.area import economy as econ, traffic_hazards as th
from apps.area.http import SourceError

FIX = Path('tests/fixtures/real/area')
KINGSTON = (41.9651857, -73.9889473)
CYPRESS = (26.546031, -81.876662)
BPS = {'2609': 'cur_ytd', '2512': 'last_dec', '2509': 'prev_ytd', '2412': 'prev_dec', '2409': 'prev2_ytd'}


def raw(name):
    return (FIX / name).read_bytes()


class FixedDate(date):
    @classmethod
    def today(cls):
        return cls(2026, 11, 19)


@pytest.fixture(autouse=True)
def frozen_today(monkeypatch):
    monkeypatch.setattr(econ, 'date', FixedDate)
    monkeypatch.setattr(th, 'date', FixedDate)
    import apps.area.http as http
    monkeypatch.setattr(http.time, 'sleep', lambda s: None)


class Response(io.BytesIO):
    status = 200
    def __enter__(self):
        return self
    def __exit__(self, *a):
        return False


class FixtureOpener:
    """Serves recorded real responses for one site; anything unrecorded is a 404."""
    def __init__(self, site):
        self.site, self.calls = site, []

    def open(self, request, timeout=None):
        url = request.full_url
        self.calls.append(url)
        parts = urlsplit(url)
        q = parse_qs(parts.query)
        if 'MapServer/82' in url:
            return Response(raw(f'{self.site}.county.json'))
        if 'cew/data/api/2026/1/area/36111.csv' in url:
            return Response(raw('ulster.qcew.csv'))
        if 'publicAPI' in url:
            return Response(raw(f'{self.site}.laus.json'))
        if '/econ/bps/County/co' in url:
            key = BPS.get(parts.path.rsplit('co', 1)[1][:4])
            if key:
                return Response(raw(f'bps_{key}.txt'))
        if 'HPMS_FULL_' in url:
            year = url.split('HPMS_FULL_')[1].split('/')[0].split('_')[1]
            path = FIX / f'{self.site}.hpms{year}.json'
            if path.exists():
                return Response(path.read_bytes())
        if 'NFHL' in url:
            xmin, _, xmax, _ = map(float, q['geometry'][0].split(','))
            metres = 100 if (xmax - xmin) > 0.001 else 30
            return Response(raw(f'{self.site}.nfhl{metres}m.json'))
        if 'National_Risk_Index' in url:
            return Response(raw(f'{self.site}.nri.json'))
        raise HTTPError(url, 404, 'Not Found', Message(), None)


# ---- parsers on real responses ------------------------------------------------

def test_county_resolves_connecticut_planning_region():
    assert econ.parse_county(raw('norwalk.county.json')) == {'fips': '09190', 'name': 'Western Connecticut Planning Region'}


def test_qcew_real_ulster_county_2026_q1():
    out = econ.parse_qcew(raw('ulster.qcew.csv'), '36111')
    assert out['10']['value'] == 47301 and out['10']['yoy_pct'] == pytest.approx(0.048)
    assert out['44-45']['value'] == 8358 and out['44-45']['establishments'] > 0


def test_qcew_suppression_is_not_zero():
    text = raw('ulster.qcew.csv').decode()
    header, *rows = text.splitlines()
    cols = header.replace('"', '').split(',')
    idx = cols.index('disclosure_code')
    patched = [header]
    for row in rows:
        cells = row.split(',')
        if cells[1] == '"5"' and cells[2] == '"44-45"':
            cells[idx] = '"N"'
        patched.append(','.join(cells))
    out = econ.parse_qcew('\n'.join(patched).encode(), '36111')
    assert out['44-45'] == {'label': 'Retail trade', 'value': None, 'reason': 'SUPPRESSED'}


def test_quarter_discovery_order():
    assert list(econ.quarters_back(date(2026, 11, 19), 3)) == [(2026, 3), (2026, 2), (2026, 1)]
    assert list(econ.quarters_back(date(2026, 2, 1), 2)) == [(2025, 4), (2025, 3)]


def test_laus_real_rate_and_year_over_year_change():
    out = econ.parse_laus(raw('kingston.laus.json'), '36111')
    assert out['period'] == '2026-09' and out['rate'] == pytest.approx(0.038)
    assert out['preliminary'] is True and out['seasonally_adjusted'] is False
    assert out['change_pts'] == pytest.approx(out['rate'] * 100 - out['prior_rate'] * 100, abs=1e-9)


def test_bps_trailing_twelve_months_from_year_to_date_files():
    files = {k: raw(f'bps_{k}.txt') for k in BPS.values()}
    assert econ.bps_months(202609) == {'cur_ytd': (2026, 9), 'last_dec': (2025, 12), 'prev_ytd': (2025, 9),
        'prev_dec': (2024, 12), 'prev2_ytd': (2024, 9)}
    out = econ.bps_trailing(files, '36111')
    assert (out['value'], out['prior']) == (739, 421)
    assert econ.bps_trailing(files, '99999')['reason'] == 'NOT_COVERED'


def test_hpms_field_aliases_across_years_and_traffic_change():
    current = th.parse_hpms(raw('kingston.hpms2025.json'))
    prior = th.parse_hpms(raw('kingston.hpms2024.json'))
    road = th.primary_roads(current)[0]
    assert th.road_label(road) == 'Ulster Ave US 9W' and road['aadt'] == 22422 and road['year'] == 2025
    change = th.traffic_change(road, prior)
    assert change['prior_aadt'] == 22523 and change['change_pct'] == pytest.approx(-0.00448, abs=1e-4)
    assert th.traffic_change({**road, 'route_id': 'other'}, prior)['reason'] == 'GEOGRAPHY_CHANGED'


def test_flood_and_nri_real_cypress_lake():
    flood = th.parse_flood(raw('cypress.nfhl30m.json'))
    assert flood['zone'] == 'AE' and flood['sfha'] is True and flood['bfe_ft'] == 9.0 and flood['risk'] == 'high'
    nri = th.parse_nri(raw('cypress.nri.json'))
    assert nri['version'] == 'December 2025' and nri['top_hazards'][0] == {'hazard': 'Hurricane', 'rating': 'Very High'}
    assert th.parse_flood(b'{"features":[]}') == {'zone': None, 'reason': 'NOT_COVERED'}
    with pytest.raises(SourceError):
        th.parse_nri(b'{"error":{"code":400}}')


# ---- service, API and job ---------------------------------------------------------

def setup(tmp_path, client, lat, lon, settings):
    from django.contrib.auth import get_user_model
    from apps.accounts.models import Membership
    from apps.sources.catalog import sync_catalog
    from apps.locations.service import change_pin
    sync_catalog()
    settings.SOURCE_ARTIFACT_ROOT = tmp_path / 'artifacts'
    user = get_user_model().objects.create_user(username='m@example.org', email='m@example.org')
    Membership.objects.create(email='m@example.org', user=user, role='member')
    client.force_login(user)
    created = client.post('/api/locations/', {'name': 'Site', 'address': '1 Main St'}, content_type='application/json').json()
    return change_pin(location_id=created['id'], expected_version=created['version'], lat=lat, lon=lon, actor=user)


@pytest.mark.django_db
def test_service_computes_all_sections_from_real_responses_and_reuses_snapshots(tmp_path, client, settings):
    from apps.area.service import compute_area
    from apps.sources.models import SourceSnapshot
    location = setup(tmp_path, client, *KINGSTON, settings)
    opener = FixtureOpener('kingston')
    three = ('economy', 'traffic', 'hazards')
    rows = {r.section: r for r in compute_area(location.pk, sections=three, opener=opener)}
    assert {k: r.status for k, r in rows.items()} == {'economy': 'available', 'traffic': 'available', 'hazards': 'available'}
    econ_data = rows['economy'].data
    assert econ_data['county']['name'] == 'Ulster County' and econ_data['employment']['period'] == '2026 Q1'
    assert econ_data['permits']['value'] == 739 and econ_data['permits']['period'] == '12 months to 2026-09'
    assert rows['traffic'].data['roads'][0]['aadt'] == 22422
    assert {s['id'] for s in rows['economy'].sources} >= {'SRC-04', 'SRC-06', 'SRC-07', 'SRC-09'}
    published = SourceSnapshot.objects.count()
    again = FixtureOpener('kingston')
    compute_area(location.pk, sections=three, opener=again)
    assert again.calls == [] and SourceSnapshot.objects.count() == published
    body = client.get(f'/api/locations/{location.pk}/area/').json()
    assert body['sections']['hazards']['status'] == 'available'


@pytest.mark.django_db
def test_flood_zone_raises_a_concern(tmp_path, client, settings):
    from apps.area.service import compute_area
    location = setup(tmp_path, client, *CYPRESS, settings)
    hazards = {r.section: r for r in compute_area(location.pk, sections=('hazards',), opener=FixtureOpener('cypress'))}['hazards']
    assert hazards.data['concerns'][0].startswith('Pin is in FEMA zone AE')


@pytest.mark.django_db
def test_one_failing_source_does_not_blank_other_sections(tmp_path, client, settings):
    from apps.area.service import compute_area

    class NoFlood(FixtureOpener):
        def open(self, request, timeout=None):
            if 'NFHL' in request.full_url:
                raise OSError('connection reset')
            return super().open(request, timeout)
    location = setup(tmp_path, client, *KINGSTON, settings)
    rows = {r.section: r for r in compute_area(location.pk, sections=('economy', 'traffic', 'hazards'),
        opener=NoFlood('kingston'))}
    assert rows['economy'].status == 'available' and rows['traffic'].status == 'available'
    assert rows['hazards'].data['flood_at_pin'] == {'value': None, 'reason': 'SOURCE_ERROR'}
    assert rows['hazards'].data['nri']['rating'] == 'Relatively Moderate'


@pytest.mark.django_db
def test_api_requires_pin_auth_and_marks_stale_after_pin_move(tmp_path, client, settings):
    from apps.area.service import compute_area
    from apps.locations.service import change_pin
    location = setup(tmp_path, client, *KINGSTON, settings)
    url = f'/api/locations/{location.pk}/area/'
    assert client.get(url).json()['sections']['economy']['reason'] == 'NOT_COMPUTED'
    compute_area(location.pk, sections=('traffic',), opener=FixtureOpener('kingston'))
    location.refresh_from_db()
    change_pin(location_id=location.pk, expected_version=location.version, lat=41.97, lon=-73.99, actor=None)
    assert client.get(url).json()['sections']['traffic']['reason'] == 'STALE'
    client.logout()
    assert client.get(url).status_code == 403


@pytest.mark.django_db
def test_post_enqueues_one_job_per_analysis_version(tmp_path, client, settings):
    from apps.operations.models import JobRun
    location = setup(tmp_path, client, *KINGSTON, settings)
    url = f'/api/locations/{location.pk}/area/'
    first, second = client.post(url), client.post(url)
    assert first.status_code == 202 and first.json()['job_id'] == second.json()['job_id']
    assert JobRun.objects.get(kind='compute_area_profile').parameters['analysis_version'] == location.analysis_version


# ---- nearby businesses (Overture) -------------------------------------------------

from apps.area import businesses as biz, overture

KPIN = (41.965186, -73.988947)  # Kingston seed reference pin used by the archived captures


def kingston(release):
    return json.loads(raw(f'kingston.overture.{release}.0p6mi.json'))


def test_brand_normalization_and_anchor_matching():
    assert biz.normalize_brand("DICK'S Sporting Goods") == biz.normalize_brand("Dick's Sporting Goods") == 'dicks sporting goods'
    assert biz.normalize_brand('Stop & Shop') == 'stop shop'
    assert biz.brand_in("Lowe's Home Improvement", biz.ANCHOR_BRANDS)
    assert not biz.brand_in('Lowell Pharmacy', biz.ANCHOR_BRANDS)
    assert biz.normalize_brand(None) is None


def test_real_regal_closure_is_a_watch_level_possible_closure():
    found = biz.changes(kingston('2026-09-23.1'), kingston('2026-10-21.0'), KPIN)
    regal = [c for c in found['closures'] if c['name'] == 'Regal Cinemas Hudson Valley Mall 12']
    assert len(regal) == 1 and regal[0]['severity'] == 'Watch' and regal[0]['evidence'] == 'marked permanently closed'
    assert regal[0]['distance_mi'] == pytest.approx(0.25, abs=0.05)


def test_null_to_open_and_low_confidence_are_not_changes():
    base = {'id': 'a', 'name': 'CVS Pharmacy', 'brand': 'CVS Pharmacy', 'basic_category': 'pharmacy_and_drug_store',
        'lat': KPIN[0], 'lon': KPIN[1], 'sources': None}
    assert biz.changes([{**base, 'operating_status': None, 'confidence': 0.9}],
        [{**base, 'operating_status': 'open', 'confidence': 0.9}], KPIN) == {'closures': [], 'openings': []}
    assert biz.changes([{**base, 'operating_status': 'open', 'confidence': 0.5}], [], KPIN)['closures'] == []
    gone = biz.changes([{**base, 'operating_status': 'open', 'confidence': 0.9}], [], KPIN)['closures'][0]
    assert gone['severity'] == 'FYI' and gone['evidence'] == 'no longer in the dataset'  # Watch, one level lower
    mine = biz.changes([{**base, 'operating_status': 'open', 'confidence': 0.9}],
        [{**base, 'operating_status': 'permanently_closed', 'confidence': 0.9}], KPIN, ['CVS'])['closures'][0]
    assert mine['severity'] == 'High' and mine['tenant_match'] is True


def test_landscape_counts_and_anchors_from_real_kingston_data():
    out = biz.landscape(kingston('2026-11-18.0'), KPIN, radii=(0.5,))
    assert out['retail_and_services_total']['0.5mi'] > 100
    assert all(a['brand'] for a in out['anchors'])
    assert out['anchors'] == sorted(out['anchors'], key=lambda a: a['distance_mi'])
    assert 'Regal Cinemas Hudson Valley Mall 12' not in [a['name'] for a in out['anchors']]


def test_broad_change_guard():
    assert biz.broad_change([(100, 130)] * 4) is None
    assert biz.broad_change([(100, 130)] * 3 + [(100, 100)] * 4) is True
    assert biz.broad_change([(100, 101)] * 10) is False


def test_release_listing_keeps_newest_per_month():
    assert overture.parse_releases(raw('overture-releases.xml'))[-3:] == ['2026-09-23.1', '2026-10-21.0', '2026-11-18.0']


class ListingOpener(FixtureOpener):
    def open(self, request, timeout=None):
        if 'overturemaps-us-west-2' in request.full_url:
            return Response(raw('overture-releases.xml'))
        return super().open(request, timeout)


@pytest.mark.django_db
def test_businesses_section_captures_missing_releases_once_and_diffs(tmp_path, client, settings):
    from apps.area.service import compute_area
    location = setup(tmp_path, client, *KPIN, settings)
    calls = []

    def capturer(lat, lon, release):
        calls.append(release)
        return json.dumps(kingston(release)).encode()
    row = compute_area(location.pk, sections=('businesses',), opener=ListingOpener('kingston'), capturer=capturer)[0]
    assert sorted(calls) == ['2026-10-21.0', '2026-11-18.0']
    assert row.status == 'available' and row.data['release'] == '2026-11-18.0'
    assert row.data['prior_release'] == '2026-10-21.0' and row.data['changes']['reason'] is None
    assert any(s['id'] == 'SRC-13' for s in row.sources)
    compute_area(location.pk, sections=('businesses',), opener=ListingOpener('kingston'), capturer=capturer)
    assert len(calls) == 2  # stored captures are reused


@pytest.mark.django_db
def test_businesses_unavailable_when_capture_fails(tmp_path, client, settings):
    from apps.area.service import compute_area
    location = setup(tmp_path, client, *KPIN, settings)

    def broken(lat, lon, release):
        raise SourceError('SOURCE_ERROR', 'S3 unreachable')
    row = compute_area(location.pk, sections=('businesses',), opener=ListingOpener('kingston'), capturer=broken)[0]
    assert row.status == 'unavailable' and row.data == {'reason': 'SOURCE_ERROR'}


# ---- jobs located in each ring (LODES) ---------------------------------------------

from apps.area import jobs as lodes

NORWALK = (41.126611, -73.388299)
GEO_FIX = Path('tests/fixtures/real/ring_demographics/norwalk_444_westport_5mi.geography.json')


def norwalk_blocks():
    from apps.demographics import geography
    capture = geography.GeographyCapture.from_payload(GEO_FIX.read_bytes(), datetime.now(timezone.utc))
    return geography.parse_geography(capture)[0]


def test_real_lodes_ring_jobs_norwalk():
    wac = lodes.parse_wac(raw('ct_wac_S000_JT00_2024.norwalk5mi.csv.gz'))
    prior = lodes.parse_wac(raw('ct_wac_S000_JT00_2023.norwalk5mi.csv.gz'))
    blocks = norwalk_blocks()
    now, before = lodes.ring_jobs(blocks, wac, NORWALK, (1, 3, 5)), lodes.ring_jobs(blocks, prior, NORWALK, (1, 3, 5))
    # Verified 2026-11-19 against the live files: 5,453 / 45,424 / 68,013 jobs in 2024.
    assert [now[r]['total'] for r in (1, 3, 5)] == [5453, 45424, 68013]
    assert now[3]['retail'] == 5729 and now[3]['food_service'] == 4021
    trend = lodes.with_trend(now[3], before[3])
    assert trend['prior_total'] == 44253 and trend['change_pct'] == pytest.approx(0.0265, abs=1e-3)


def test_jobs_trend_needs_one_thousand_jobs_and_bad_files_fail_closed():
    small = {'total': 900, 'retail': 1, 'food_service': 1, 'workplace_blocks': 3}
    assert lodes.with_trend(small, {**small, 'total': 950})['change_reason'] == 'NOT_ENOUGH_DATA'
    assert lodes.with_trend(small, None)['change_pct'] is None
    with pytest.raises(SourceError):
        lodes.parse_wac(b'not gzip')
    import gzip as gz
    with pytest.raises(SourceError):
        lodes.parse_wac(gz.compress(b'w_geocode,C000\n123,4\n'))


class LodesOpener(FixtureOpener):
    def open(self, request, timeout=None):
        url = request.full_url
        if 'lehd.ces.census.gov' in url:
            self.calls.append(request.get_method() + ' ' + url)
            year = url.rsplit('_', 1)[1][:4]
            path = FIX / f'ct_wac_S000_JT00_{year}.norwalk5mi.csv.gz'
            if not path.exists():
                raise HTTPError(url, 404, 'Not Found', Message(), None)
            return Response(b'' if request.get_method() == 'HEAD' else path.read_bytes())
        return super().open(request, timeout)


@pytest.mark.django_db
def test_jobs_section_reuses_ring_geography_and_lodes_snapshots(tmp_path, client, settings):
    from apps.area.service import compute_area
    from apps.demographics import geography
    from apps.sources.storage import LocalArtifactStore
    location = setup(tmp_path, client, *NORWALK, settings)
    store = LocalArtifactStore(tmp_path / 'artifacts')
    geography.publish_capture(geography.GeographyCapture.from_payload(GEO_FIX.read_bytes(),
        datetime(2026, 11, 19, tzinfo=timezone.utc)), store)
    opener = LodesOpener('norwalk')
    row = compute_area(location.pk, sections=('jobs',), opener=opener, store=store)[0]
    assert row.status == 'available' and row.data['year'] == 2024 and row.data['prior_year'] == 2023
    assert [r['total'] for r in row.data['rings']] == [5453, 45424, 68013]
    assert {s['id'] for s in row.sources} == {'SRC-04', 'SRC-05'}
    assert sum(1 for c in opener.calls if c.startswith('GET') and 'lehd' in c) == 2   # 2024 and 2023
    again = LodesOpener('norwalk')
    compute_area(location.pk, sections=('jobs',), opener=again, store=store)
    assert not any(c.startswith('GET') for c in again.calls if 'lehd' in c)  # year checks only, no re-downloads


# ---- T1: source health and stale fallback ------------------------------------------

@pytest.mark.django_db
def test_fetches_record_health_and_failures_fall_back_to_last_good(tmp_path, client, settings):
    from datetime import timedelta
    from django.utils import timezone
    from apps.area.service import compute_area
    from apps.sources.models import SourceHealth, SourceSnapshot
    from apps.sources.health import health_status
    location = setup(tmp_path, client, *KINGSTON, settings)
    compute_area(location.pk, sections=('economy',), opener=FixtureOpener('kingston'))
    laus = SourceHealth.objects.get(source_id='SRC-07', scope='laus:36111')
    assert health_status(laus) == 'OK' and laus.latest_snapshot is not None
    # Age the LAUS snapshot past its 7-day freshness window, then break the network.
    from django.db import connection
    with connection.cursor() as cur:
        cur.execute('UPDATE sources_sourcesnapshot SET retrieved_at=%s WHERE source_id=%s',
            [timezone.now() - timedelta(days=30), 'SRC-07'])
        cur.execute('UPDATE sources_sourcehealth SET last_success_at=%s, last_checked_at=%s WHERE source_id=%s',
            [timezone.now() - timedelta(days=30), timezone.now() - timedelta(days=30), 'SRC-07'])

    class Down(FixtureOpener):
        def open(self, request, timeout=None):
            if 'publicAPI' in request.full_url:
                raise OSError('down')
            return super().open(request, timeout)
    row = compute_area(location.pk, sections=('economy',), opener=Down('kingston'))[0]
    laus.refresh_from_db()
    assert health_status(laus) == 'Failing' and laus.error_code == 'SOURCE_ERROR'
    assert row.data['unemployment']['rate'] == pytest.approx(0.038)  # last good value still shown
    entry = next(s for s in row.sources if s['id'] == 'SRC-07')
    assert entry['stale'] is True and entry['stale_reason'] == 'SOURCE_ERROR'
    body = client.get(f'/api/locations/{location.pk}/area/').json()
    assert body['sections']['economy']['stale'] is True
    sources = {s['id']: s for s in client.get('/api/sources/').json()}
    assert sources['SRC-07']['status'] == 'Failing' and sources['SRC-06']['status'] == 'OK'
