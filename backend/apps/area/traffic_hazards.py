"""Traffic counts (FHWA HPMS, SRC-10) and hazards (FEMA NFHL SRC-11, FEMA NRI SRC-12)."""
import json
from datetime import date
import math
import re
from .http import fetch, arcgis_json, SourceError

HPMS_URL = 'https://geo.dot.gov/server/rest/services/Hosted/HPMS_FULL_{st}_{year}/FeatureServer/0/query'
NFHL_URL = 'https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer/28/query'
NRI_URL = 'https://services.arcgis.com/XG15cJAlne2vxtgt/arcgis/rest/services/National_Risk_Index_Census_Tracts/FeatureServer/0/query'
STATES = {'01': 'AL', '02': 'AK', '04': 'AZ', '05': 'AR', '06': 'CA', '08': 'CO', '09': 'CT', '10': 'DE', '11': 'DC',
    '12': 'FL', '13': 'GA', '15': 'HI', '16': 'ID', '17': 'IL', '18': 'IN', '19': 'IA', '20': 'KS', '21': 'KY',
    '22': 'LA', '23': 'ME', '24': 'MD', '25': 'MA', '26': 'MI', '27': 'MN', '28': 'MS', '29': 'MO', '30': 'MT',
    '31': 'NE', '32': 'NV', '33': 'NH', '34': 'NJ', '35': 'NM', '36': 'NY', '37': 'NC', '38': 'ND', '39': 'OH',
    '40': 'OK', '41': 'OR', '42': 'PA', '44': 'RI', '45': 'SC', '46': 'SD', '47': 'TN', '48': 'TX', '49': 'UT',
    '50': 'VT', '51': 'VA', '53': 'WA', '54': 'WV', '55': 'WI', '56': 'WY'}
TRAFFIC_RADIUS_M = 250
HPMS_FIELDS = 'route_id,routename,routenumber,aadt,data_year,f_system,through_lanes,begin_point,end_point'
F_SYSTEM = {1: 'Interstate', 2: 'Freeway/expressway', 3: 'Principal arterial', 4: 'Minor arterial',
    5: 'Major collector', 6: 'Minor collector', 7: 'Local'}


# ---- HPMS traffic ---------------------------------------------------------------

# HPMS field names differ by data year (2023: routeid/beginpoint; 2024: routename;
# 2025: route_name/route_number), so request all fields and normalize aliases.
ALIASES = {'route_id': ('route_id', 'routeid'), 'name': ('route_name', 'routename'),
    'number': ('route_number', 'routenumber'), 'year': ('data_year', 'datayear'),
    'begin': ('begin_point', 'beginpoint'), 'end': ('end_point', 'endpoint')}


def _pick(a, key):
    return next((a[k] for k in ALIASES[key] if a.get(k) not in (None, '')), None)


def fetch_hpms(state_fips, year, lat, lon, *, opener=None):
    st = STATES.get(state_fips)
    if st is None:
        raise SourceError('NOT_COVERED', 'unsupported state')
    url = HPMS_URL.format(st=st, year=year)
    raw = fetch(url, params={'geometry': f'{lon},{lat}', 'geometryType': 'esriGeometryPoint', 'inSR': 4326,
        'spatialRel': 'esriSpatialRelIntersects', 'distance': TRAFFIC_RADIUS_M, 'units': 'esriSRUnit_Meter',
        'outFields': '*', 'returnGeometry': 'true', 'outSR': 4326, 'geometryPrecision': 6, 'f': 'json'},
        opener=opener, max_bytes=16 * 1024 * 1024)
    return raw, url


def fetch_hpms_latest(state_fips, lat, lon, *, today=None, opener=None):
    """Newest published HPMS year for the state (services are per state and year)."""
    year = (today or date.today()).year
    for candidate in range(year - 1, year - 5, -1):
        try:
            raw, url = fetch_hpms(state_fips, candidate, lat, lon, opener=opener)
            arcgis_json(raw)
            return raw, url, candidate
        except SourceError as exc:
            if exc.code not in ('NOT_COVERED', 'SOURCE_ERROR'):
                raise
    raise SourceError('NOT_COVERED', 'no HPMS year published for this state')


RAMP_OR_SERVICE = {4, 5, 6}   # HPMS facility_type: ramp, non-mainline, non-inventory direction
FULL_ACCESS_CONTROL = 1       # HPMS access_control: limited-access highway (no driveway to the center)


def _count_year(a):
    """Year of the traffic count behind the AADT (aadt_vd), which can be older than data_year."""
    vd = a.get('aadt_vd')
    if isinstance(vd, str) and vd[:4].isdigit():
        return int(vd[:4])
    if isinstance(vd, (int, float)) and vd > 10_000_000_000:  # epoch milliseconds
        from datetime import datetime, timezone
        return datetime.fromtimestamp(vd / 1000, tz=timezone.utc).year
    return None


def _distance_m(paths, lat, lon):
    if not paths:
        return None
    k = 111_320
    cx = math.cos(math.radians(lat))
    best = None
    for path in paths:
        pts = [((x - lon) * k * cx, (y - lat) * k) for x, y in path]
        for (ax, ay), (bx, by) in zip(pts, pts[1:]):
            dx, dy = bx - ax, by - ay
            length = dx * dx + dy * dy
            t = 0 if length == 0 else max(0.0, min(1.0, -(ax * dx + ay * dy) / length))
            d = math.hypot(ax + t * dx, ay + t * dy)
            best = d if best is None or d < best else best
    return None if best is None else round(best)


def parse_hpms(raw, lat=None, lon=None):
    try:
        features = json.loads(raw).get('features')
    except ValueError:
        raise SourceError('SCHEMA_ERROR', 'not JSON') from None
    arcgis_json(raw)  # raises on ArcGIS errors
    segments = []
    for f in features or []:
        a = f.get('attributes') or {}
        route_id, aadt = _pick(a, 'route_id'), a.get('aadt')
        if not aadt or not route_id:
            continue
        name = _pick(a, 'name')
        number = _pick(a, 'number')
        paths = (f.get('geometry') or {}).get('paths')
        segments.append({'route_id': str(route_id), 'name': (str(name).strip() or None) if name else None,
            'number': number, 'aadt': int(aadt), 'year': _pick(a, 'year'), 'count_year': _count_year(a),
            'f_system': a.get('f_system'), 'facility_type': a.get('facility_type'),
            'access_control': a.get('access_control'), 'lanes': a.get('through_lanes'),
            'begin': _pick(a, 'begin'), 'end': _pick(a, 'end'),
            'distance_m': _distance_m(paths, lat, lon) if lat is not None else None})
    return segments


def road_label(segment):
    if segment['name']:
        label = segment['name'].title().replace('Us ', 'US ')
        # Route designators stay upper case: "NC-87", "SR-2100", "I-95", "US 9W".
        # Drop internal inventory codes in front of a street name ("G039 Fifteenth St", "EV2L Kindred St").
        label = re.sub(r'^(?=\S*\d)[A-Za-z0-9]{3,5}\s+(?=[A-Za-z])', '', label) if not re.match(r'^\d', label) else label
        label = re.sub(r'\b(\d+)(St|Nd|Rd|Th)\b', lambda m: m.group(1) + m.group(2).lower(), label)
        label = re.sub(r'\b(Ne|Nw|Se|Sw)\b', lambda m: m.group(1).upper(), label)
        return re.sub(r'\b([A-Za-z]{1,3})(-?\d+[A-Za-z]?)\b', lambda m: m.group(1).upper() + m.group(2).upper(), label)
    if segment['number']:
        return f"Route {segment['number']}"
    return F_SYSTEM.get(segment['f_system'], 'Road')


def serves_the_site(s):
    """Roads a shopper can drive in from: not ramps, service roads or limited-access highways."""
    return s.get('facility_type') not in RAMP_OR_SERVICE and s.get('access_control') != FULL_ACCESS_CONTROL \
        and s.get('f_system') != 1


def _class_bucket(s):
    f = s.get('f_system') or 9
    return 0 if f <= 4 else 1 if f <= 6 else 2  # arterials, collectors, local


def primary_roads(segments, limit=2):
    """docs/04 §3.5: up to two distinct routes that serve the site: arterials before collectors
    before local roads, then the nearest; the segment nearest the pin gives each route's count.
    Ramps and limited-access highways are used only when nothing else is within range."""
    usable = [s for s in segments if serves_the_site(s)] or segments
    far = 10 ** 6
    by_route = {}
    for s in sorted(usable, key=lambda s: (s['distance_m'] if s.get('distance_m') is not None else far, -s['aadt'])):
        key = s['name'] or s['number'] or s['route_id']
        by_route.setdefault(key, s)
    ranked = sorted(by_route.values(), key=lambda s: (_class_bucket(s),
        s['distance_m'] if s.get('distance_m') is not None else far, s['f_system'] or 9, -s['aadt']))
    return ranked[:limit]


def traffic_change(current, prior_segments):
    """Same route with the largest overlap in the prior year. A change is reported only when the
    count behind the AADT is newer; otherwise the state carried an estimate forward (SAME_COUNT)."""
    best, overlap = None, 0
    for p in prior_segments:
        if p['route_id'] != current['route_id'] or p['begin'] is None or current['begin'] is None:
            continue
        o = min(p['end'], current['end']) - max(p['begin'], current['begin'])
        if o > overlap:
            best, overlap = p, o
    if best is None:
        return {'prior_aadt': None, 'change_pct': None, 'reason': 'GEOGRAPHY_CHANGED'}
    out = {'prior_aadt': best['aadt'], 'prior_year': best['year'], 'count_year': current.get('count_year'),
        'prior_count_year': best.get('count_year')}
    if current.get('count_year') and current.get('count_year') == best.get('count_year'):
        return {**out, 'change_pct': None, 'reason': 'SAME_COUNT'}
    return {**out, 'change_pct': (current['aadt'] - best['aadt']) / best['aadt'] if best['aadt'] else None, 'reason': None}


# ---- FEMA flood zones ---------------------------------------------------------

def envelope(lat, lon, metres):
    dlat = metres / 111_320
    dlon = metres / (111_320 * max(0.01, math.cos(math.radians(lat))))
    return f'{lon - dlon},{lat - dlat},{lon + dlon},{lat + dlat}'


def fetch_flood(lat, lon, metres, *, opener=None, geometry=False):
    # Point queries failed 5 of 7 times in verification; small envelopes succeed (docs/03 SRC-11).
    params = {'geometry': envelope(lat, lon, metres), 'geometryType': 'esriGeometryEnvelope',
        'inSR': 4326, 'spatialRel': 'esriSpatialRelIntersects',
        'outFields': 'FLD_ZONE,ZONE_SUBTY,SFHA_TF,STATIC_BFE,DFIRM_ID', 'returnGeometry': 'false', 'f': 'json'}
    if geometry:
        # Only high-risk (SFHA) polygons, in lon/lat, to measure the distance from the pin.
        params.update({'where': "SFHA_TF='T'", 'returnGeometry': 'true', 'outSR': 4326, 'geometryPrecision': 6})
    return fetch(NFHL_URL, params=params, opener=opener, timeout=45, retries=3)


def _local_xy(lat0, lon0, lat, lon):
    k = 111_320
    return (lon - lon0) * k * math.cos(math.radians(lat0)), (lat - lat0) * k


def _segment_distance(ax, ay, bx, by):
    """Distance from the origin to segment AB, in the same units."""
    dx, dy = bx - ax, by - ay
    length = dx * dx + dy * dy
    t = 0 if length == 0 else max(0.0, min(1.0, -(ax * dx + ay * dy) / length))
    return math.hypot(ax + t * dx, ay + t * dy)


def _contains_origin(rings):
    """Even-odd rule over all rings, so holes (islands of lower risk) are excluded."""
    inside = False
    for ring in rings:
        for (ax, ay), (bx, by) in zip(ring, ring[1:] + ring[:1]):
            if (ay > 0) != (by > 0) and 0 < (bx - ax) * (0 - ay) / (by - ay) + ax:
                inside = not inside
    return inside


def parse_flood_nearby(raw, lat, lon):
    """High-risk (SFHA) flood zones around the pin: whether the pin is inside one and how far the nearest is."""
    try:
        data = json.loads(raw)
    except ValueError:
        raise SourceError('SCHEMA_ERROR', 'not JSON') from None
    if 'error' in data or not isinstance(data.get('features'), list):
        raise SourceError('SOURCE_ERROR', 'ArcGIS query failed')
    best = None
    for f in data['features']:
        a = f.get('attributes') or {}
        if a.get('SFHA_TF') != 'T' or not a.get('FLD_ZONE'):
            continue
        rings = [[_local_xy(lat, lon, y, x) for x, y in ring] for ring in (f.get('geometry') or {}).get('rings') or []]
        if rings:
            inside = _contains_origin(rings)
            dist = 0.0 if inside else min(_segment_distance(*p, *q) for r in rings for p, q in zip(r, r[1:] + r[:1]))
        else:
            inside, dist = False, None  # geometry missing: known nearby, distance unknown
        zone = {'zone': a['FLD_ZONE'], 'sfha': True, 'inside': inside,
            'distance_m': None if dist is None else round(dist), 'dfirm_id': a.get('DFIRM_ID'), 'reason': None}
        key = (not inside, dist if dist is not None else 1e9)
        if best is None or key < best[0]:
            best = (key, zone)
    if best is None:
        return {'zone': None, 'sfha': False, 'inside': False, 'distance_m': None, 'reason': None}
    return best[1]


def zone_rank(z):
    if z['sfha']:
        return 3 if z['zone'].startswith('V') else 2
    if '0.2' in (z['subtype'] or ''):
        return 1
    return 0


def parse_flood(raw):
    zones = []
    for a in arcgis_json(raw):
        if not a.get('FLD_ZONE'):
            continue
        bfe = a.get('STATIC_BFE')
        zones.append({'zone': a['FLD_ZONE'], 'subtype': a.get('ZONE_SUBTY'), 'sfha': a.get('SFHA_TF') == 'T',
            'bfe_ft': None if bfe in (None, -9999, -9999.0) else bfe, 'dfirm_id': a.get('DFIRM_ID')})
    if not zones:
        return {'zone': None, 'reason': 'NOT_COVERED'}
    top = max(zones, key=zone_rank)
    return {**top, 'reason': None, 'risk': ['minimal', 'moderate', 'high', 'high_coastal'][zone_rank(top)]}


# ---- FEMA National Risk Index ---------------------------------------------------

NRI_HAZARDS = {'CFLD': 'Coastal flooding', 'IFLD': 'Inland flooding', 'HRCN': 'Hurricane', 'TRND': 'Tornado',
    'SWND': 'Strong wind', 'WNTW': 'Winter weather', 'HAIL': 'Hail', 'HWAV': 'Heat wave', 'WFIR': 'Wildfire',
    'ERQK': 'Earthquake', 'LTNG': 'Lightning', 'ISTM': 'Ice storm', 'DRGT': 'Drought',
    'LNDS': 'Landslide', 'CWAV': 'Cold wave'}
# Hazards that damage buildings and disrupt a center for weeks; lightning, heat or cold do not.
PROPERTY_HAZARDS = {'Coastal flooding', 'Inland flooding', 'Hurricane', 'Wildfire', 'Earthquake', 'Landslide'}
RATING_ORDER = ['Very Low', 'Relatively Low', 'Relatively Moderate', 'Relatively High', 'Very High']


def fetch_nri(lat, lon, *, opener=None):
    fields = ','.join(['TRACTFIPS', 'RISK_RATNG', 'RISK_SPCTL', 'NRI_VER'] + [f'{h}_RISKR' for h in NRI_HAZARDS])
    return fetch(NRI_URL, params={'geometry': f'{lon},{lat}', 'geometryType': 'esriGeometryPoint', 'inSR': 4326,
        'spatialRel': 'esriSpatialRelIntersects', 'outFields': fields, 'returnGeometry': 'false', 'f': 'json'},
        opener=opener)


def parse_nri(raw):
    rows = arcgis_json(raw)
    if not rows:
        return {'rating': None, 'reason': 'NOT_COVERED'}
    a = rows[0]
    hazards = [{'hazard': name, 'rating': a.get(f'{code}_RISKR')} for code, name in NRI_HAZARDS.items()
        if a.get(f'{code}_RISKR') in RATING_ORDER]
    hazards.sort(key=lambda h: -RATING_ORDER.index(h['rating']))
    # Concern comes from specific hazards rated high, not the composite score (which is mostly
    # population and building value, so dense areas rate "high" regardless of physical risk).
    high = [h for h in hazards if h['rating'] in ('Relatively High', 'Very High') and h['hazard'] in PROPERTY_HAZARDS]
    return {'tract': a.get('TRACTFIPS'), 'rating': a.get('RISK_RATNG'),
        'percentile': None if a.get('RISK_SPCTL') is None else round(a['RISK_SPCTL'], 1),
        'version': a.get('NRI_VER'), 'top_hazards': hazards[:3], 'reason': None,
        'high_hazards': [h['hazard'] for h in high], 'concern': bool(high)}
