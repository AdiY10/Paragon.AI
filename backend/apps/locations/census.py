"""Bounded Census address lookup. Never log provider URLs containing addresses."""
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
import re
import socket
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, build_opener, HTTPRedirectHandler

ENDPOINT = 'https://geocoding.geo.census.gov/geocoder/geographies/onelineaddress'
ADAPTER_VERSION = 'census-single-v1'
MAX_BYTES = 1_048_576
GEOGRAPHIES = {
    'States': ('state', 2, 'Current_Current'),
    'Counties': ('county', 5, 'Current_Current'),
    'Census Tracts': ('tract', 11, 'Current_Current'),
    'Census Block Groups': ('block_group', 12, 'Current_Current'),
    '2020 Census Blocks': ('block', 15, 'Census2020'),
}


class GeocoderError(Exception):
    def __init__(self, code):
        if code not in {'TIMEOUT','HTTP_ERROR','SCHEMA_ERROR','SOURCE_ERROR','NOT_CONFIGURED','STORAGE_ERROR'}:
            raise ValueError('Invalid geocoder error code')
        self.code = code
        super().__init__(code)


class NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


@dataclass(frozen=True)
class CensusResult:
    status: str
    candidates: tuple[dict, ...]
    benchmark: dict
    vintage: dict


@dataclass(frozen=True)
class CensusCapture:
    result: CensusResult
    raw: bytes
    sha256: str
    retrieved_at: datetime


def normalized_address(value):
    if not isinstance(value, str) or len(value) > 500 or any(ord(c) < 32 for c in value):
        raise ValueError('A single-line address of at most 500 characters is required')
    value = ' '.join(value.split())
    if not value:
        raise ValueError('An address is required')
    return value


def _label(value, maximum):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise GeocoderError('SCHEMA_ERROR')
    return value


def _version(value, name_key, expected):
    if not isinstance(value, dict) or value.get(name_key) != expected:
        raise GeocoderError('SCHEMA_ERROR')
    identifier = value.get('id')
    if not isinstance(identifier, str) or not re.fullmatch(r'[0-9]{1,16}', identifier):
        raise GeocoderError('SCHEMA_ERROR')
    return {'id': identifier, 'name': expected}


def parse_census(raw):
    if not isinstance(raw, bytes) or len(raw) > MAX_BYTES:
        raise GeocoderError('SCHEMA_ERROR')
    try:
        payload = json.loads(raw)
        result = payload['result']
        benchmark = _version(result['input']['benchmark'], 'benchmarkName', 'Public_AR_Current')
        vintage = _version(result['input']['vintage'], 'vintageName', 'Current_Current')
        matches = result['addressMatches']
        if not isinstance(matches, list) or len(matches) > 20:
            raise GeocoderError('SCHEMA_ERROR')
        candidates = []
        for match in matches:
            coords = match['coordinates']
            lat, lon = coords['y'], coords['x']
            if any(type(v) not in (int,float) or not math.isfinite(v) for v in (lat,lon)) or not -90 <= lat <= 90 or not -180 <= lon <= 180:
                raise GeocoderError('SCHEMA_ERROR')
            geographies = match['geographies']
            if not isinstance(geographies, dict):
                raise GeocoderError('SCHEMA_ERROR')
            resolved = {}
            for label, (kind, length, geography_vintage) in GEOGRAPHIES.items():
                entries = geographies.get(label, [])
                if not isinstance(entries, list) or len(entries) > 1:
                    raise GeocoderError('SCHEMA_ERROR')
                if not entries:
                    continue
                geoid = entries[0]['GEOID']
                if not isinstance(geoid, str) or not re.fullmatch(r'[0-9]{'+str(length)+'}', geoid):
                    raise GeocoderError('SCHEMA_ERROR')
                resolved[kind] = {'geoid':geoid,'name':_label(entries[0]['NAME'],500),
                    'geography_vintage':geography_vintage}
            # A lookup without geography may still place a pin; missing geography
            # stays absent and must be resolved before downstream calculations.
            candidates.append({'lat':float(lat),'lon':float(lon),
                'matched_address':_label(match['matchedAddress'],500),
                'method':'census_interpolated','match_quality':'not_reported',
                'geographies':resolved})
        # One-line JSON does not report Exact/Non_Exact. Never infer that claim
        # from string similarity, nor silently pick the first ambiguous result.
        status = 'no_match' if not candidates else 'matched' if len(candidates)==1 else 'ambiguous'
        return CensusResult(status,tuple(candidates),benchmark,vintage)
    except GeocoderError:
        raise
    except (ValueError,TypeError,KeyError,IndexError,AttributeError,OverflowError):
        raise GeocoderError('SCHEMA_ERROR') from None


def fetch_census(address, *, opener=None, timeout=10):
    address = normalized_address(address)
    params = {'address':address,'benchmark':'Public_AR_Current','vintage':'Current_Current',
        'layers':'all','format':'json'}
    request = Request(ENDPOINT+'?'+urlencode(params), headers={
        'User-Agent':'ParagonRadar/0.1 (+https://github.com/AdiY10/Paragon.AI)',
        'Accept':'application/json'})
    try:
        with (opener or _opener()).open(request,timeout=timeout) as response:
            if response.status != 200:
                raise GeocoderError('HTTP_ERROR')
            if response.headers.get_content_type() != 'application/json':
                raise GeocoderError('SCHEMA_ERROR')
            raw = response.read(MAX_BYTES+1)
        result = parse_census(raw)
        echo = json.loads(raw)['result']['input']['address']['address']
        if normalized_address(echo).casefold() != address.casefold():
            raise GeocoderError('SCHEMA_ERROR')
        return CensusCapture(result,raw,hashlib.sha256(raw).hexdigest(),datetime.now(timezone.utc))
    except GeocoderError:
        raise
    except (TimeoutError,socket.timeout):
        raise GeocoderError('TIMEOUT') from None
    except HTTPError:
        raise GeocoderError('HTTP_ERROR') from None
    except URLError as exc:
        raise GeocoderError('TIMEOUT' if isinstance(exc.reason,(TimeoutError,socket.timeout)) else 'SOURCE_ERROR') from None
    except (OSError,ValueError,TypeError,KeyError):
        raise GeocoderError('SOURCE_ERROR') from None


def _opener():
    from apps.area.http import HostAllowlist
    return build_opener(HostAllowlist(), NoRedirects())


POINT_ENDPOINT = 'https://geocoding.geo.census.gov/geocoder/geographies/coordinates'
PLACE_SUFFIX = re.compile(r'\s+(city|town|village|borough|CDP|municipality|township)$', re.I)


def fetch_point_geographies(lat, lon, *, opener=None, timeout=10):
    """State, county and place at a map point (Census coordinates service; redesign B5).

    Returns {'state', 'state_fips', 'county', 'county_fips', 'place'} or None outside the US.
    """
    params = {'x': f'{lon:.6f}', 'y': f'{lat:.6f}', 'benchmark': 'Public_AR_Current', 'vintage': 'Current_Current',
        'layers': 'all', 'format': 'json'}
    request = Request(POINT_ENDPOINT + '?' + urlencode(params), headers={
        'User-Agent': 'ParagonRadar/0.1 (+https://github.com/AdiY10/Paragon.AI)', 'Accept': 'application/json'})
    try:
        with (opener or _opener()).open(request, timeout=timeout) as response:
            if response.status != 200:
                raise GeocoderError('HTTP_ERROR')
            raw = response.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise GeocoderError('SCHEMA_ERROR')
        geos = json.loads(raw)['result']['geographies']
    except GeocoderError:
        raise
    except (TimeoutError, socket.timeout):
        raise GeocoderError('TIMEOUT') from None
    except HTTPError:
        raise GeocoderError('HTTP_ERROR') from None
    except URLError as exc:
        raise GeocoderError('TIMEOUT' if isinstance(exc.reason, (TimeoutError, socket.timeout)) else 'SOURCE_ERROR') from None
    except (OSError, ValueError, TypeError, KeyError):
        raise GeocoderError('SCHEMA_ERROR') from None
    first = lambda key: (geos.get(key) or [None])[0] or {}  # noqa: E731
    state = first('States')
    if not state.get('STUSAB'):
        return None
    county = first('Counties')
    place = first('Incorporated Places') or first('Census Designated Places') or first('County Subdivisions')
    name = PLACE_SUFFIX.sub('', place.get('NAME') or '') or None
    return {'state': state['STUSAB'], 'state_fips': state.get('STATE') or state.get('GEOID'),
        'county': county.get('NAME'), 'county_fips': county.get('GEOID'), 'place': name}
