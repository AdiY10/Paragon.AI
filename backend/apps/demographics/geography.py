"""2020 Census blocks and block-group totals around a pin from TIGERweb (SRC-04).

Also resolves each 2020 block group to the GEOID used by the ACS vintage. These
match everywhere except Connecticut, whose 2022 switch to planning regions
changed county codes but kept tract and block-group numbers. Tract and
block-group suffixes repeat statewide in CT, so we match only against ACS
block groups that intersect the same search area, and fail closed on any
ambiguity (docs/04 §3.4).
"""
from dataclasses import dataclass
from datetime import datetime, timezone
import io
import json
import math
from urllib.parse import urlencode
from urllib.request import Request
from apps.area.http import default_opener
from apps.sources.snapshots import publish_snapshot, ValidationReport
from .rings import Block, BlockGroupTotals

ADAPTER_VERSION = 'tigerweb-blocks-v1'
BASE = 'https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb'
BLOCKS_URL = f'{BASE}/tigerWMS_Census2020/MapServer/10/query'
BG2020_URL = f'{BASE}/tigerWMS_Census2020/MapServer/8/query'
ACS_BG_URL = f'{BASE}/tigerWMS_ACS{{year}}/MapServer/10/query'
# 2010 blocks and block groups: the geography of the ACS 2015-2019 trend baseline.
BLOCKS_2010_URL = f'{BASE}/tigerWMS_Census2010/MapServer/18/query'
BG2010_URL = f'{BASE}/tigerWMS_Census2010/MapServer/16/query'
DECENNIAL = {2020: (BLOCKS_URL, BG2020_URL), 2010: (BLOCKS_2010_URL, BG2010_URL)}
MAX_BYTES = 64 * 1024 * 1024
PAGE = 50_000
# Blocks are selected by intersection; internal points can sit slightly outside
# the ring for edge blocks, so search a little wider and filter by internal point.
SEARCH_MARGIN_MILES = 0.25


class GeographyError(Exception):
    pass


def _get(url, params, opener, timeout):
    request = Request(url + '?' + urlencode(params),
        headers={'User-Agent': 'ParagonRadar/0.1 (+https://github.com/AdiY10/Paragon.AI)'})
    with (opener or default_opener()).open(request, timeout=timeout) as response:
        if response.status != 200:
            raise GeographyError(f'HTTP {response.status}')
        raw = response.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise GeographyError('TIGERweb response exceeds size limit')
    data = json.loads(raw)
    if 'error' in data or not isinstance(data.get('features'), list):
        raise GeographyError('TIGERweb query failed')
    return data


def _paged(url, params, opener, timeout):
    features, offset = [], 0
    while True:
        data = _get(url, {**params, 'resultOffset': offset, 'resultRecordCount': PAGE}, opener, timeout)
        features.extend(f['attributes'] for f in data['features'])
        if not data.get('exceededTransferLimit'):
            return features
        offset += len(data['features'])
        if not data['features']:
            raise GeographyError('TIGERweb pagination stalled')


def _near(lat, lon, miles):
    return {'geometry': f'{lon},{lat}', 'geometryType': 'esriGeometryPoint', 'inSR': 4326,
        'spatialRel': 'esriSpatialRelIntersects', 'distance': miles,
        'units': 'esriSRUnit_StatuteMile', 'returnGeometry': 'false', 'f': 'json'}


@dataclass(frozen=True)
class GeographyCapture:
    lat: float
    lon: float
    radius_miles: float
    acs_year: int
    blocks: list            # raw attribute dicts
    bg_totals: list
    acs_block_groups: list
    retrieved_at: datetime
    decennial: int = 2020

    def payload(self):
        return json.dumps({'lat': self.lat, 'lon': self.lon, 'radius_miles': self.radius_miles,
            'acs_year': self.acs_year, 'blocks': self.blocks, 'bg_totals': self.bg_totals,
            'acs_block_groups': self.acs_block_groups, 'decennial': self.decennial}, sort_keys=True, separators=(',', ':')).encode()

    @classmethod
    def from_payload(cls, raw, retrieved_at):
        d = json.loads(raw)
        return cls(d['lat'], d['lon'], d['radius_miles'], d['acs_year'], d['blocks'],
            d['bg_totals'], d['acs_block_groups'], retrieved_at, d.get('decennial', 2020))


def fetch_geography(lat, lon, radius_miles, *, acs_year, decennial=2020, opener=None, timeout=60):
    if decennial not in DECENNIAL:
        raise GeographyError('Unsupported decennial geography')
    blocks_url, bg_url = DECENNIAL[decennial]
    if not (math.isfinite(lat) and math.isfinite(lon) and abs(lat) <= 90 and abs(lon) <= 180):
        raise GeographyError('Invalid pin')
    search = radius_miles + SEARCH_MARGIN_MILES
    blocks = _paged(blocks_url, {**_near(lat, lon, search),
        'outFields': 'GEOID,POP100,AREALAND,INTPTLAT,INTPTLON'}, opener, timeout)
    bgs = sorted({g[:12] for b in blocks if isinstance(g := b.get('GEOID'), str) and len(g) == 15 and g.isdigit()})
    totals = []
    for i in range(0, len(bgs), 200):
        chunk = bgs[i:i + 200]
        where = 'GEOID IN (' + ','.join(f"'{g}'" for g in chunk) + ')'
        totals.extend(_paged(bg_url, {'where': where, 'outFields': 'GEOID,POP100,AREALAND',
            'returnGeometry': 'false', 'f': 'json'}, opener, timeout))
    # ACS 2015-2019 uses 2010 block groups unchanged, so no code mapping is needed.
    acs_bgs = [] if decennial == 2010 else _paged(ACS_BG_URL.format(year=acs_year),
        {**_near(lat, lon, search), 'outFields': 'GEOID'}, opener, timeout)
    return GeographyCapture(lat, lon, radius_miles, acs_year, blocks, totals, acs_bgs,
        datetime.now(timezone.utc), decennial)


def parse_geography(capture):
    """Validate a capture and return (blocks, totals by 2020 BG, 2020 BG -> ACS GEOID)."""
    blocks = []
    for a in capture.blocks:
        geoid = a.get('GEOID')
        if not (isinstance(geoid, str) and len(geoid) == 15 and geoid.isdigit()):
            raise GeographyError('Invalid block GEOID')
        try:
            blocks.append(Block(geoid, int(a['POP100']), int(a['AREALAND']),
                float(a['INTPTLAT']), float(a['INTPTLON'])))
        except (KeyError, TypeError, ValueError):
            raise GeographyError('Malformed block record') from None
    totals = {}
    for a in capture.bg_totals:
        totals[a['GEOID']] = BlockGroupTotals(int(a['POP100']), int(a['AREALAND']))
    missing = {b.block_group for b in blocks} - set(totals)
    if missing:
        raise GeographyError(f'Missing 2020 block-group totals for {len(missing)} block groups')
    if capture.decennial == 2010:
        return blocks, totals, {bg: bg for bg in {b.block_group for b in blocks}}, set()
    acs = {a['GEOID'] for a in capture.acs_block_groups}
    by_suffix = {}
    for geoid in acs:
        by_suffix.setdefault((geoid[:2], geoid[5:]), []).append(geoid)
    mapping, unresolved = {}, set()
    for bg in {b.block_group for b in blocks}:
        if bg in acs:
            mapping[bg] = bg
            continue
        candidates = by_suffix.get((bg[:2], bg[5:]), [])
        if len(candidates) == 1:
            mapping[bg] = candidates[0]
        else:
            unresolved.add(bg)
    return blocks, totals, mapping, unresolved


def scope_for(lat, lon, radius_miles, decennial=2020):
    return f'blocks{decennial}:{lat:.6f},{lon:.6f}:r{radius_miles:g}'


def publish_capture(capture, store):
    payload = capture.payload()
    return publish_snapshot(source_id='SRC-04',
        scope=scope_for(capture.lat, capture.lon, capture.radius_miles, capture.decennial),
        release=f'Census{capture.decennial}+ACS{capture.acs_year}', data_period=f'{capture.decennial} Census blocks',
        source_url=DECENNIAL[capture.decennial][0], adapter_version=ADAPTER_VERSION, stream=io.BytesIO(payload),
        store=store, retrieved_at=capture.retrieved_at,
        validation=ValidationReport(True, True, {'fields': ['GEOID', 'POP100', 'AREALAND', 'INTPTLAT', 'INTPTLON']},
            len(capture.blocks)),
        context={'lat': capture.lat, 'lon': capture.lon, 'radius_miles': capture.radius_miles,
            'acs_year': capture.acs_year, 'decennial': capture.decennial})


def load_capture(snapshot, store):
    with store.open_verified(snapshot.artifact_key) as handle:
        return GeographyCapture.from_payload(handle.read(), snapshot.retrieved_at)
