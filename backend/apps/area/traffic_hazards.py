"""Traffic counts (FHWA HPMS, SRC-10) and hazards (FEMA NFHL SRC-11, FEMA NRI SRC-12)."""
from datetime import date
import math
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
        'outFields': '*', 'returnGeometry': 'false', 'f': 'json'}, opener=opener, max_bytes=8 * 1024 * 1024)
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


def parse_hpms(raw):
    segments = []
    for a in arcgis_json(raw):
        route_id, aadt = _pick(a, 'route_id'), a.get('aadt')
        if not aadt or not route_id:
            continue
        name = _pick(a, 'name')
        number = _pick(a, 'number')
        segments.append({'route_id': str(route_id), 'name': (str(name).strip() or None) if name else None,
            'number': number, 'aadt': int(aadt), 'year': _pick(a, 'year'), 'f_system': a.get('f_system'),
            'lanes': a.get('through_lanes'), 'begin': _pick(a, 'begin'), 'end': _pick(a, 'end')})
    return segments


def road_label(segment):
    if segment['name']:
        return segment['name'].title().replace('Us ', 'US ')
    if segment['number']:
        return f"Route {segment['number']}"
    return F_SYSTEM.get(segment['f_system'], 'Road')


def primary_roads(segments, limit=2):
    """docs/04 §3.5: up to two distinct named routes, highest class then highest AADT."""
    best = {}
    for s in sorted(segments, key=lambda s: (s['f_system'] or 9, -s['aadt'])):
        key = s['name'] or s['number'] or s['route_id']
        if key not in best:
            best[key] = s
    return list(best.values())[:limit]


def traffic_change(current, prior_segments):
    """Same route ID with overlapping measures in the prior year; otherwise no comparison."""
    for p in prior_segments:
        if p['route_id'] == current['route_id'] and p['begin'] is not None and current['begin'] is not None \
                and p['begin'] < current['end'] and current['begin'] < p['end']:
            return {'prior_aadt': p['aadt'], 'prior_year': p['year'],
                'change_pct': (current['aadt'] - p['aadt']) / p['aadt'] if p['aadt'] else None, 'reason': None}
    return {'prior_aadt': None, 'change_pct': None, 'reason': 'GEOGRAPHY_CHANGED'}


# ---- FEMA flood zones ---------------------------------------------------------

def envelope(lat, lon, metres):
    dlat = metres / 111_320
    dlon = metres / (111_320 * max(0.01, math.cos(math.radians(lat))))
    return f'{lon - dlon},{lat - dlat},{lon + dlon},{lat + dlat}'


def fetch_flood(lat, lon, metres, *, opener=None):
    # Point queries failed 5 of 7 times in verification; small envelopes succeed (docs/03 SRC-11).
    return fetch(NFHL_URL, params={'geometry': envelope(lat, lon, metres), 'geometryType': 'esriGeometryEnvelope',
        'inSR': 4326, 'spatialRel': 'esriSpatialRelIntersects',
        'outFields': 'FLD_ZONE,ZONE_SUBTY,SFHA_TF,STATIC_BFE,DFIRM_ID', 'returnGeometry': 'false', 'f': 'json'},
        opener=opener, timeout=45, retries=3)


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
    return {'tract': a.get('TRACTFIPS'), 'rating': a.get('RISK_RATNG'),
        'percentile': None if a.get('RISK_SPCTL') is None else round(a['RISK_SPCTL'], 1),
        'version': a.get('NRI_VER'), 'top_hazards': hazards[:3], 'reason': None,
        'concern': a.get('RISK_RATNG') in ('Relatively High', 'Very High')}
