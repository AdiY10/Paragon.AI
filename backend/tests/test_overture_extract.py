"""Redesign B4b: local US Overture extract (build, validate, query, prune)."""
import json
import pytest
from apps.area import overture_extract as ox
from apps.area.http import SourceError


def source_file(tmp_path, n=50, lat=41.0, lon=-73.0, name='src.parquet'):
    """A tiny file in the Overture places schema (struct columns as in the release)."""
    import duckdb
    path = tmp_path / name
    con = duckdb.connect()
    con.execute(f"""COPY (SELECT 'p' || i AS id, {{'primary': 'Place ' || i}} AS names, 'restaurant' AS basic_category,
        {{'names': {{'primary': NULL}}, 'wikidata': NULL}} AS brand, 'open' AS operating_status, 0.9 AS confidence,
        {{'xmin': {lon} + i * 0.001, 'ymin': {lat} + i * 0.001}} AS bbox
        FROM range({n}) t(i)
        UNION ALL SELECT 'paris', {{'primary': 'Cafe'}}, 'cafe', {{'names': {{'primary': NULL}}, 'wikidata': NULL}}, 'open',
            0.9, {{'xmin': 2.35, 'ymin': 48.85}}) TO '{path}' (FORMAT parquet)""")
    con.close()
    return str(path)


@pytest.fixture
def root(tmp_path, settings):
    settings.SOURCE_ARTIFACT_ROOT = tmp_path / 'artifacts'
    return tmp_path


def test_build_keeps_us_rows_and_queries_locally(root):
    m = ox.build('2026-11-18.0', source=source_file(root))
    assert m['rows'] == 50 and m['bytes'] > 0 and len(m['sha256']) == 64  # Paris dropped
    assert ox.available() == ['2026-11-18.0'] and ox.build('2026-11-18.0') == m  # idempotent
    rows = json.loads(ox.capture_local(41.0, -73.0, '2026-11-18.0', radius=1.0))
    assert rows and {'id', 'name', 'lat', 'lon', 'brand', 'confidence'} <= set(rows[0])
    assert all(r['lat'] >= 41.0 for r in rows) and rows == sorted(rows, key=lambda r: r['id'])
    assert ox.capture_local(41.0, -73.0, '2026-10-21.0') is None  # no extract for that release


def test_a_suspicious_row_count_is_refused(root):
    ox.build('2026-10-21.0', source=source_file(root, n=100, name='a.parquet'))
    with pytest.raises(SourceError):
        ox.build('2026-11-18.0', source=source_file(root, n=50, name='b.parquet'))  # -50%
    assert ox.available() == ['2026-10-21.0'] and not list((root / 'overture-extract').glob('*.part'))


def test_capture_falls_back_to_s3(root, monkeypatch):
    monkeypatch.setattr('apps.area.overture.capture', lambda lat, lon, release, radius=3.0: b'[]')
    assert ox.capture(41.0, -73.0, '2026-11-18.0') == b'[]'


def test_prune_keeps_the_newest_three(root):
    for i, rel in enumerate(['2026-08-20.0', '2026-09-23.1', '2026-10-21.0', '2026-11-18.0']):
        ox.build(rel, source=source_file(root, n=50, name=f'{i}.parquet'))
    assert ox.prune() == 1 and ox.available() == ['2026-09-23.1', '2026-10-21.0', '2026-11-18.0']


def test_invalid_release_names_are_refused(root):
    with pytest.raises(SourceError):
        ox.path_for('../../etc')


@pytest.mark.django_db
def test_a_pin_reads_the_local_extract_instead_of_s3(root, monkeypatch):
    from apps.sources.catalog import sync_catalog
    from apps.sources.storage import LocalArtifactStore
    from apps.area.service import Run, businesses_section
    sync_catalog()
    ox.build('2026-11-18.0', source=source_file(root))

    def no_s3(*a, **k):
        raise AssertionError('S3 must not be read when a local extract exists')
    monkeypatch.setattr('apps.area.overture.capture', no_s3)
    monkeypatch.setattr('apps.area.service.overture_releases', lambda run: ['2026-11-18.0'])
    data, ok = businesses_section(Run(LocalArtifactStore(root / 'artifacts'), None), 41.0, -73.0)
    assert ok and data['release'] == '2026-11-18.0' and data['retail_and_services_total']['1mi'] >= 0
