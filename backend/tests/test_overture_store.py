"""R2 item 14: compact Overture captures, release-pair guard, pruning."""
import json
import pytest
from apps.area import overture_store as ostore
from apps.sources.storage import LocalArtifactStore

pytestmark = pytest.mark.django_db


def rec(pid, brand=None, lat=41.0, lon=-73.0, cat='fashion_and_apparel_store'):
    return {'id': pid, 'name': brand or pid, 'brand': brand, 'basic_category': cat, 'confidence': 0.95,
        'operating_status': 'open', 'lat': lat, 'lon': lon, 'sources': [{'big': 'x' * 500}]}


def test_compact_round_trip_drops_sources(tmp_path):
    store = LocalArtifactStore(tmp_path)
    records = [rec(f'p{i}') for i in range(50)]
    cap = ostore.store_capture(41.0, -73.0, '2026-11-18.0', records, store)
    back = ostore.load(cap, store)
    assert len(back) == 50 and 'sources' not in back[0] and back[0]['id'] == 'p0'
    assert (tmp_path / cap.compact_key).stat().st_size < len(json.dumps(records)) / 20
    assert cap.summary['one_mile_count'] == 50


def test_pair_flags_brand_wide_drops_by_distinct_place(tmp_path):
    store = LocalArtifactStore(tmp_path)
    pins = [(41.0 + i / 10, -73.0) for i in range(5)]
    for n, (lat, lon) in enumerate(pins):
        before = [rec(f'lidl{n}', 'Lidl', lat, lon), rec(f'cvs{n}', 'CVS', lat, lon)]
        after = [rec(f'cvs{n}', 'CVS', lat, lon)] + ([rec(f'lidl{n}', 'Lidl', lat, lon)] if n == 0 else [])
        ostore.store_capture(lat, lon, 'r1', before, store)
        ostore.store_capture(lat, lon, 'r2', after, store)
    row = ostore.pair('r1', 'r2')
    assert row.cohort_size == 5 and row.brand_drops == ['lidl']


def test_prune_keeps_compact_copy(tmp_path):
    import io
    from apps.sources.catalog import sync_catalog
    from apps.sources.snapshots import publish_snapshot, ValidationReport
    sync_catalog()
    store = LocalArtifactStore(tmp_path)
    raw = json.dumps([rec('a')]).encode()
    snap, _ = publish_snapshot(source_id='SRC-13', scope='pin:x', release='r0', data_period='Overture r0',
        source_url='https://x', adapter_version='t', stream=io.BytesIO(raw), store=store,
        validation=ValidationReport(True, True, {'format': 'raw'}, 1),
        context={'coordinates': {'lat': 41.0, 'lon': -73.0}, 'radius_miles': 3})
    cap = ostore.get_capture(41.0, -73.0, 'r0', store)
    assert cap.raw_snapshot_id == snap.pk
    assert ostore.prune_raw(store, ['r1', 'r2']) == 1
    assert not (tmp_path / snap.artifact_key).exists() and ostore.load(cap, store)[0]['id'] == 'a'


def test_disappearance_alerts_only_after_two_releases(tmp_path, client, settings):
    from backend.tests.test_signals import placed
    from apps.area.service import compute_area
    from apps.insights.models import Signal
    settings.SOURCE_ARTIFACT_ROOT = tmp_path
    store = LocalArtifactStore(tmp_path)
    loc = placed('Mall', 41.0, -73.0)
    regal = rec('regal', 'Regal', 41.003, -73.0, 'movie_theater')
    keep = [rec(f'k{i}', None, 41.001, -73.0) for i in range(3)]
    releases = ['2026-09-23.1', '2026-10-21.0', '2026-11-18.0']
    from apps.area import overture

    def run(upto, present):
        for rel, has in zip(releases[:upto], present):
            ostore.store_capture(41.0, -73.0, rel, keep + ([regal] if has else []), store)
        import unittest.mock as um
        # The release listing is a cached probe (1 day, B4a); a new release mid-day is stubbed directly.
        with um.patch('apps.area.service.overture_releases', lambda run: releases[:upto]):
            return compute_area(loc.pk, sections=('businesses',), store=store)[0]
    row = run(2, [True, False])
    assert row.data['changes']['closures'][0]['confirmed'] is False
    assert not Signal.objects.filter(rule_id='SIG-09').exists()
    row = run(3, [True, False, False])
    c = row.data['changes']['closures'][0]
    assert c['confirmed'] is True and c['evidence'] == 'missing from the last two releases'
    assert Signal.objects.filter(rule_id='SIG-09', status='active').exists()
