"""Overture release discovery and on-demand 3-mile captures (SRC-13).

Seed properties already have archived captures imported via
``import_overture_captures``; this module covers new or moved pins.
"""
import json
import math
from pathlib import Path
import re
import xml.etree.ElementTree as ET
from django.conf import settings
from apps.demographics.rings import haversine_miles
from .http import fetch, SourceError

BUCKET = 'https://overturemaps-us-west-2.s3.us-west-2.amazonaws.com/'
RELEASE = re.compile(r'^\d{4}-\d{2}-\d{2}\.\d+$')
COLUMNS = ['id', 'name', 'basic_category', 'brand', 'brand_wikidata', 'operating_status', 'confidence', 'lat', 'lon']


def parse_releases(xml):
    """Newest release per month, oldest first (e.g. 2026-09-23.1 supersedes 2026-09-23.0)."""
    months = {}
    for el in ET.fromstring(xml).iter():
        if el.tag.split('}')[-1] != 'Prefix':
            continue
        name = (el.text or '').strip('/').removeprefix('release/')
        if RELEASE.fullmatch(name):
            key = (name[:10], int(name.rsplit('.', 1)[1]))
            if name[:7] not in months or key > months[name[:7]][0]:
                months[name[:7]] = (key, name)
    return [months[m][1] for m in sorted(months)]


def available_releases(*, opener=None):
    raw = fetch(BUCKET, params={'list-type': 2, 'prefix': 'release/', 'delimiter': '/'}, opener=opener)
    releases = parse_releases(raw)
    if not releases:
        raise SourceError('SCHEMA_ERROR', 'no Overture releases listed')
    return releases


def source_url(release):
    return f's3://overturemaps-us-west-2/release/{release}/theme=places/type=place/*'


def _box(lat, lon, radius):
    delta = (radius + 0.05) / 69.0
    dx = delta / max(0.01, math.cos(math.radians(lat)))
    return lon - dx, lon + dx, lat - delta, lat + delta


def _connect(duckdb):
    import os
    ext = Path(settings.SOURCE_ARTIFACT_ROOT).parent / 'duckdb-extensions'
    ext.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(config={'extension_directory': str(ext)})
    con.execute("INSTALL httpfs; LOAD httpfs; INSTALL spatial; LOAD spatial;")
    # Small hosts: OVERTURE_MEMORY_LIMIT (e.g. 256MB) keeps DuckDB inside the container's RAM.
    limit = os.environ.get('OVERTURE_MEMORY_LIMIT', '1GB')
    if not re.fullmatch(r'\d+(MB|GB)', limit):
        limit = '1GB'
    con.execute(f"SET s3_region='us-west-2'; SET memory_limit='{limit}'; SET threads=2;")
    return con


SELECT = """SELECT id, names.primary AS name, basic_category, brand.names.primary AS brand,
    brand.wikidata AS brand_wikidata, operating_status, confidence, ST_Y(geometry) AS lat, ST_X(geometry) AS lon
    FROM read_parquet(?) WHERE """


def capture_many(pins, release, radius=3.0):
    """One DuckDB session and one scan for several pins: {(lat, lon): JSON bytes}.

    Only the fields the product uses are read (no per-record ``sources``), which keeps
    memory small on a 2 GB server.
    """
    import duckdb
    if not RELEASE.fullmatch(release):
        raise SourceError('SCHEMA_ERROR', 'invalid release')
    pins = list(pins)
    if not pins:
        return {}
    boxes = [_box(lat, lon, radius) for lat, lon in pins]
    where = ' OR '.join('(bbox.xmin BETWEEN ? AND ? AND bbox.ymin BETWEEN ? AND ?)' for _ in boxes)
    params = [source_url(release)] + [v for b in boxes for v in b]
    from .locks import overture_capture_lock
    with overture_capture_lock():
        try:
            con = _connect(duckdb)
            try:
                rows = con.execute(SELECT + where, params).fetchall()
            finally:
                con.close()
        except Exception as exc:
            raise SourceError('SOURCE_ERROR', type(exc).__name__) from None
    records = [dict(zip(COLUMNS, r)) for r in rows]
    out = {}
    for lat, lon in pins:
        mine = [r for r in records if haversine_miles(lat, lon, r['lat'], r['lon']) <= radius]
        mine.sort(key=lambda r: r['id'])
        out[(lat, lon)] = json.dumps(mine, sort_keys=True, default=str).encode()
    return out


def capture(lat, lon, release, radius=3.0):
    """Read places within ``radius`` miles from the public GeoParquet release (DuckDB, ~10-60 s)."""
    return capture_many([(lat, lon)], release, radius)[(lat, lon)]
