"""Preserve bounded real Places extracts before Overture release retention expires."""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import re
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

BUCKET = 'https://overturemaps-us-west-2.s3.us-west-2.amazonaws.com/'
RELEASE = re.compile(r'^\d{4}-\d{2}-\d{2}\.\d+$')


def monthly_releases(xml: bytes, count: int = 2) -> list[str]:
    releases = {}
    for element in ET.fromstring(xml).iter():
        if element.tag.split('}')[-1] != 'Prefix':
            continue
        candidate = (element.text or '').strip('/').removeprefix('release/')
        if RELEASE.fullmatch(candidate):
            month = candidate[:7]
            key = (candidate[:10], int(candidate.rsplit('.', 1)[1]))
            if month not in releases or key > releases[month][0]:
                releases[month] = (key, candidate)
    result = [releases[m][1] for m in sorted(releases, reverse=True)[:count]]
    if len(result) < count:
        raise ValueError(f'Need {count} distinct monthly releases; found {len(result)}')
    return sorted(result)


def distance_miles(lat1, lon1, lat2, lon2):
    a, b = math.radians(lat1), math.radians(lat2)
    dlat, dlon = b-a, math.radians(lon2-lon1)
    h = math.sin(dlat/2)**2 + math.cos(a)*math.cos(b)*math.sin(dlon/2)**2
    return 3958.7613 * 2 * math.asin(math.sqrt(min(1, max(0, h))))


def valid_capture(path: Path) -> bool:
    manifest_path = path.with_suffix('.manifest.json')
    if not path.exists() or not manifest_path.exists():
        return False
    manifest = json.loads(manifest_path.read_text())
    return manifest.get('sha256') == hashlib.sha256(path.read_bytes()).hexdigest()


def capture(con, release, site, destination):
    if not RELEASE.fullmatch(release):
        raise ValueError('Invalid release identifier')
    lat, lon = float(site['reference_lat']), float(site['reference_lon'])
    target = destination / release / f"{site['seed_id']}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    if valid_capture(target):
        return {'status': 'cached', 'path': str(target)}
    # A conservative bbox prunes Parquet row groups; exact spherical distance follows.
    delta = 3.05 / 69.0
    dx = delta / math.cos(math.radians(lat))
    url = f's3://overturemaps-us-west-2/release/{release}/theme=places/type=place/*'
    rows = con.execute('''SELECT id, names.primary AS name, basic_category,
        brand.names.primary AS brand, operating_status, confidence, sources,
        ST_Y(geometry) AS lat, ST_X(geometry) AS lon
        FROM read_parquet(?) WHERE bbox.xmin BETWEEN ? AND ?
        AND bbox.ymin BETWEEN ? AND ?''', [url, lon-dx, lon+dx, lat-delta, lat+delta])
    columns = [d[0] for d in rows.description]
    records = []
    for row in rows.fetchall():
        record = dict(zip(columns, row))
        if distance_miles(lat, lon, record['lat'], record['lon']) <= 3:
            records.append(record)
    records.sort(key=lambda item: item['id'])
    payload = json.dumps(records, sort_keys=True, default=str).encode()
    temporary = target.with_suffix('.tmp')
    temporary.write_bytes(payload)
    temporary.replace(target)
    manifest = {'release': release, 'seed_id': site['seed_id'],
        'coordinates': {'lat': lat, 'lon': lon}, 'radius_miles': 3,
        'pin_provenance': site['source_url'], 'pin_status': 'unconfirmed_seed_reference',
        'source': url, 'retrieved_at': datetime.now(timezone.utc).isoformat(),
        'record_count': len(records), 'sha256': hashlib.sha256(payload).hexdigest(),
        'attribution_url': 'https://docs.overturemaps.org/attribution/',
        'schema': columns, 'status': 'complete'}
    temp_manifest = target.with_suffix('.manifest.tmp')
    temp_manifest.write_text(json.dumps(manifest, indent=2)+'\n')
    temp_manifest.replace(target.with_suffix('.manifest.json'))
    return {'status': 'captured', 'path': str(target), 'records': len(records)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seed', type=Path, default=Path('data/seed/paragon_public_properties.csv'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--location', action='append', help='Optional seed ID; repeatable')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(BUCKET+'?list-type=2&prefix=release/&delimiter=/',
        headers={'User-Agent': 'ParagonRadarBootstrap/0.1'})
    with urllib.request.urlopen(request, timeout=30) as response:
        listing = response.read()
    (args.output/'release-listing.xml').write_bytes(listing)
    releases = monthly_releases(listing)
    import duckdb
    extensions = args.output.resolve() / '.duckdb-extensions'
    extensions.mkdir(exist_ok=True)
    con = duckdb.connect(config={'extension_directory': str(extensions)})
    con.execute("INSTALL httpfs; LOAD httpfs; INSTALL spatial; LOAD spatial;")
    con.execute("SET s3_region='us-west-2'; SET memory_limit='1GB'; SET threads=2;")
    results = []
    with args.seed.open() as handle:
        for site in csv.DictReader(handle):
            if args.location and site['seed_id'] not in args.location:
                continue
            if not site['reference_lat'] or not site['reference_lon']:
                results.append({'seed_id': site['seed_id'], 'status': 'unresolved_pin'})
                continue
            for release in releases:
                try:
                    outcome = capture(con, release, site, args.output)
                except Exception as exc:
                    outcome = {'status': 'failed', 'error_type': type(exc).__name__, 'error': str(exc)}
                outcome.update(seed_id=site['seed_id'], release=release)
                results.append(outcome)
                print(json.dumps(outcome), flush=True)
                (args.output/'bootstrap-report.json').write_text(json.dumps(results, indent=2)+'\n')
    (args.output/'bootstrap-report.json').write_text(json.dumps(results, indent=2)+'\n')
    return 1 if any(r['status'] in ('failed', 'unresolved_pin') for r in results) else 0

if __name__ == '__main__':
    raise SystemExit(main())
