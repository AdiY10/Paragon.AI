"""County economy: QCEW employment (SRC-06), LAUS unemployment (SRC-07), BPS permits (SRC-09).

All three are county-level (Connecticut: planning regions). They describe the
local economy, not the property (docs/04 §8).
"""
import csv
from datetime import date
import io
import json
import os
from .http import fetch, arcgis_json, SourceError

COUNTY_URL = 'https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/tigerWMS_ACS2024/MapServer/82/query'
QCEW_URL = 'https://data.bls.gov/cew/data/api/{year}/{quarter}/area/{fips}.csv'
LAUS_V1 = 'https://api.bls.gov/publicAPI/v1/timeseries/data/'
LAUS_V2 = 'https://api.bls.gov/publicAPI/v2/timeseries/data/'
BPS_URL = 'https://www2.census.gov/econ/bps/County/co{yymm}y.txt'
INDUSTRIES = {'10': 'Total, all private industries', '44-45': 'Retail trade'}


# ---- county at pin --------------------------------------------------------------

def fetch_county(lat, lon, *, opener=None):
    raw = fetch(COUNTY_URL, params={'geometry': f'{lon},{lat}', 'geometryType': 'esriGeometryPoint',
        'inSR': 4326, 'spatialRel': 'esriSpatialRelIntersects', 'outFields': 'GEOID,NAME',
        'returnGeometry': 'false', 'f': 'json'}, opener=opener)
    return raw


def parse_county(raw):
    rows = arcgis_json(raw)
    if len(rows) != 1 or not str(rows[0].get('GEOID', '')).isdigit() or len(rows[0]['GEOID']) != 5:
        raise SourceError('NOT_COVERED', 'no single county at pin')
    return {'fips': rows[0]['GEOID'], 'name': rows[0]['NAME']}


# ---- QCEW ---------------------------------------------------------------------

def quarters_back(today, count=8):
    """Candidate (year, quarter) pairs, newest first, starting with the last completed quarter."""
    year, quarter = today.year, (today.month - 1) // 3
    if quarter == 0:
        year, quarter = year - 1, 4
    for _ in range(count):
        yield year, quarter
        quarter -= 1
        if quarter == 0:
            year, quarter = year - 1, 4


def fetch_qcew_latest(fips, *, today=None, opener=None):
    """Return (raw, year, quarter, url) for the newest published quarter."""
    for year, quarter in quarters_back(today or date.today()):
        url = QCEW_URL.format(year=year, quarter=quarter, fips=fips)
        try:
            return fetch(url, opener=opener, retries=1), year, quarter, url
        except SourceError as exc:
            if exc.code != 'NOT_COVERED':
                raise
    raise SourceError('NOT_COVERED', 'no QCEW quarter published for this county')


def parse_qcew(raw, fips):
    rows = list(csv.DictReader(io.StringIO(raw.decode('utf-8'))))
    if not rows or 'oty_month3_emplvl_pct_chg' not in rows[0]:
        raise SourceError('SCHEMA_ERROR', 'unexpected QCEW layout')
    out = {}
    for code, label in INDUSTRIES.items():
        match = [r for r in rows if r['area_fips'] == fips and r['own_code'] == '5' and r['industry_code'] == code]
        if not match:
            out[code] = {'label': label, 'value': None, 'reason': 'NOT_COVERED'}
            continue
        r = match[0]
        if r['disclosure_code'].strip() == 'N':
            out[code] = {'label': label, 'value': None, 'reason': 'SUPPRESSED'}
            continue
        change = r['oty_month3_emplvl_pct_chg'].strip()
        out[code] = {'label': label, 'value': int(r['month3_emplvl']), 'establishments': int(r['qtrly_estabs']),
            'avg_weekly_wage': int(r['avg_wkly_wage']),
            'yoy_pct': None if change == '' else float(change) / 100,
            'yoy_reason': None if change != '' else 'GEOGRAPHY_CHANGED', 'reason': None}
    return out


# ---- LAUS ---------------------------------------------------------------------

def laus_series(fips):
    return f'LAUCN{fips}0000000003'


def fetch_laus(fips, *, today=None, opener=None):
    today = today or date.today()
    key = os.environ.get('BLS_API_KEY')
    body = {'seriesid': [laus_series(fips)], 'startyear': str(today.year - 2), 'endyear': str(today.year)}
    if key:
        body['registrationkey'] = key
    return fetch(LAUS_V2 if key else LAUS_V1, body=body, opener=opener), (LAUS_V2 if key else LAUS_V1)


def parse_laus(raw, fips):
    data = json.loads(raw)
    if data.get('status') != 'REQUEST_SUCCEEDED':
        raise SourceError('SOURCE_ERROR', 'BLS request not successful')
    series = data['Results']['series'][0]
    if series.get('seriesID') != laus_series(fips):
        raise SourceError('SCHEMA_ERROR', 'unexpected series')
    points = [d for d in series['data'] if d['period'].startswith('M') and d['period'] != 'M13']
    if not points:
        raise SourceError('NOT_COVERED', 'no monthly values')
    latest = points[0]
    prior = next((d for d in points if d['year'] == str(int(latest['year']) - 1) and d['period'] == latest['period']), None)
    value = float(latest['value'])
    preliminary = any(f.get('code') == 'P' for f in latest.get('footnotes', []) if f)
    out = {'rate': value / 100, 'period': f"{latest['year']}-{latest['period'][1:]}", 'preliminary': preliminary,
        'seasonally_adjusted': False}
    if prior is None or prior['value'] in ('-', ''):
        out.update(change_pts=None, change_reason='NOT_ENOUGH_DATA')
    else:
        out.update(prior_rate=float(prior['value']) / 100,
            change_pts=round(value - float(prior['value']), 2), change_reason=None)
    return out


# ---- Building Permits Survey ------------------------------------------------

def bps_months(latest_yyyymm):
    """Year-to-date files needed for the trailing and prior 12-month totals."""
    y, m = divmod(latest_yyyymm, 100)
    if m == 12:
        return {'cur_ytd': (y, 12), 'prev_ytd': (y - 1, 12)}
    return {'cur_ytd': (y, m), 'last_dec': (y - 1, 12), 'prev_ytd': (y - 1, m),
        'prev_dec': (y - 2, 12), 'prev2_ytd': (y - 2, m)}


def fetch_bps_file(year, month, *, opener=None):
    yymm = f'{year % 100:02d}{month:02d}'
    url = BPS_URL.format(yymm=yymm)
    return fetch(url, opener=opener, max_bytes=4 * 1024 * 1024), url


def latest_bps_month(*, today=None, opener=None):
    today = today or date.today()
    y, m = today.year, today.month
    for _ in range(4):
        m -= 1
        if m == 0:
            y, m = y - 1, 12
        try:
            raw, url = fetch_bps_file(y, m, opener=opener)
            return y * 100 + m, raw, url
        except SourceError as exc:
            if exc.code != 'NOT_COVERED':
                raise
    raise SourceError('NOT_COVERED', 'no recent BPS file')


def parse_bps_units(raw, fips):
    """Total units authorized (all structure sizes, with imputation) for one county."""
    state, county = fips[:2], fips[2:]
    for row in csv.reader(io.StringIO(raw.decode('latin-1'))):
        if len(row) >= 18 and row[1] == state and row[2] == county:
            try:
                return sum(int(row[i]) for i in (7, 10, 13, 16)), row[5].strip()
            except ValueError:
                raise SourceError('SCHEMA_ERROR', 'non-numeric BPS units') from None
    return None, None


def bps_trailing(files, fips):
    """``files`` maps the keys of bps_months() to raw bytes. Returns T12M, prior T12M and change."""
    units = {k: parse_bps_units(v, fips)[0] for k, v in files.items()}
    if any(v is None for v in units.values()):
        return {'value': None, 'reason': 'NOT_COVERED'}
    if 'last_dec' in units:
        current = units['cur_ytd'] + units['last_dec'] - units['prev_ytd']
        prior = units['prev_ytd'] + units['prev_dec'] - units['prev2_ytd']
    else:
        current, prior = units['cur_ytd'], units['prev_ytd']
    return {'value': current, 'prior': prior, 'change': current - prior,
        'change_pct': None if prior == 0 else (current - prior) / prior, 'reason': None}
