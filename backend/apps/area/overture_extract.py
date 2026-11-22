"""A local US-only copy of each Overture places release (redesign B4b).

New places anywhere in the US need nearby businesses fast. Reading the global release on S3 for every
pin takes 10-60 s; a one-time US extract per release (only the fields we use, zstd Parquet with
65,536-row groups, built with DuckDB capped at 512 MB and 1 thread) turns that into a sub-second local
query. The newest three releases are kept; S3 stays the fallback.

Measured on the 2 GB droplet (2026-11-22, release 2026-11-18.0): 20.8 M places, 805 MB, built in 5.4 min
inside a 900 MB container with DuckDB capped at 256 MB; a 3-mile lookup takes 0.03-0.06 s.
"""
import hashlib
import io
import json
import logging
import os
from pathlib import Path
from django.conf import settings
from apps.demographics.rings import haversine_miles
from .http import SourceError
from . import overture

log = logging.getLogger(__name__)
# Lower 48, Alaska, Hawaii, Puerto Rico (lat_min, lat_max, lon_min, lon_max).
US_BOXES = ((24.3, 49.6, -125.0, -66.8), (51.0, 71.6, -180.0, -129.9), (18.8, 22.4, -160.5, -154.6),
    (17.8, 18.6, -67.4, -65.2))
MAX_ROW_SWING = 0.15     # a new extract more than 15% bigger or smaller than the last is not trusted
KEEP = 3


def directory():
    return Path(settings.SOURCE_ARTIFACT_ROOT).parent / 'overture-extract'


def path_for(release):
    if not overture.RELEASE.fullmatch(release or ''):
        raise SourceError('SCHEMA_ERROR', 'invalid release')
    return directory() / f'{release}.parquet'


def available():
    """Releases with a finished extract, oldest first."""
    d = directory()
    return sorted(p.stem for p in d.glob('*.parquet')) if d.exists() else []


def _connect(memory='256MB', threads=1):
    import duckdb
    ext = Path(settings.SOURCE_ARTIFACT_ROOT).parent / 'duckdb-extensions'
    ext.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(config={'extension_directory': str(ext)})
    con.execute(f"SET memory_limit='{memory}'; SET threads={threads}; SET preserve_insertion_order=false;")
    return con


def build(release, *, source=None):
    """Write the US extract for a release (idempotent). Returns {'rows', 'bytes', 'sha256'}."""
    from .locks import overture_capture_lock
    final = path_for(release)
    if final.exists():
        return _manifest(final)
    final.parent.mkdir(parents=True, exist_ok=True)
    part = final.with_suffix('.parquet.part')
    where = ' OR '.join(f'(bbox.ymin BETWEEN {a} AND {b} AND bbox.xmin BETWEEN {c} AND {d})' for a, b, c, d in US_BOXES)
    src = source or overture.source_url(release)
    with overture_capture_lock():
        con = _connect()
        try:
            if source is None:
                con.execute("INSTALL httpfs; LOAD httpfs; SET s3_region='us-west-2';")
            con.execute(f"""COPY (SELECT id, names.primary AS name, basic_category, brand.names.primary AS brand,
                brand.wikidata AS brand_wikidata, operating_status, CAST(confidence AS DOUBLE) AS confidence,
                CAST(bbox.ymin AS DOUBLE) AS lat, CAST(bbox.xmin AS DOUBLE) AS lon
                FROM read_parquet(?) WHERE {where}) TO '{part}' (FORMAT parquet, COMPRESSION zstd, ROW_GROUP_SIZE 65536)""",
                [src])
            rows = con.execute('SELECT count(*) FROM read_parquet(?)', [str(part)]).fetchone()[0]
        except Exception as exc:
            part.unlink(missing_ok=True)
            raise SourceError('SOURCE_ERROR', type(exc).__name__) from None
        finally:
            con.close()
    previous = [r for r in available() if r < release]
    if previous:
        before = _manifest(path_for(previous[-1]))['rows']
        if before and abs(rows - before) / before > MAX_ROW_SWING:
            part.unlink(missing_ok=True)
            raise SourceError('SCHEMA_ERROR', f'row count {rows} vs {before} in {previous[-1]}')
    os.replace(part, final)
    manifest = _manifest(final, rows)
    log.info('Overture US extract %s: %s rows, %s bytes', release, manifest['rows'], manifest['bytes'])
    return manifest


def _manifest(path, rows=None):
    meta = path.with_suffix('.json')
    if meta.exists() and rows is None:
        return json.loads(meta.read_text())
    digest = hashlib.sha256()
    with open(path, 'rb') as handle:
        while chunk := handle.read(1 << 20):
            digest.update(chunk)
    if rows is None:
        con = _connect('256MB')
        try:
            rows = con.execute('SELECT count(*) FROM read_parquet(?)', [str(path)]).fetchone()[0]
        finally:
            con.close()
    out = {'rows': rows, 'bytes': path.stat().st_size, 'sha256': digest.hexdigest()}
    meta.write_text(json.dumps(out))
    return out


def capture_local(lat, lon, release, radius=3.0):
    """Same JSON bytes as overture.capture from the local extract, or None when there is none."""
    p = path_for(release)
    if not p.exists():
        return None
    x0, x1, y0, y1 = overture._box(lat, lon, radius)
    con = _connect('256MB')
    try:
        rows = con.execute(f"""SELECT {', '.join(overture.COLUMNS)} FROM read_parquet(?)
            WHERE lon BETWEEN ? AND ? AND lat BETWEEN ? AND ?""", [str(p), x0, x1, y0, y1]).fetchall()
    finally:
        con.close()
    records = [dict(zip(overture.COLUMNS, r)) for r in rows]
    mine = sorted((r for r in records if haversine_miles(lat, lon, r['lat'], r['lon']) <= radius), key=lambda r: r['id'])
    return json.dumps(mine, sort_keys=True, default=str).encode()


def capture(lat, lon, release, radius=3.0):
    """Local extract first, the S3 release otherwise."""
    local = capture_local(lat, lon, release, radius)
    return local if local is not None else overture.capture(lat, lon, release, radius)


def prune(keep=KEEP):
    """Keep the newest ``keep`` extracts. Returns how many were removed."""
    gone = 0
    for release in available()[:-keep] if keep else available():
        for suffix in ('.parquet', '.json'):
            path_for(release).with_suffix(suffix).unlink(missing_ok=True)
        gone += 1
    return gone
