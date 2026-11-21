"""CPI-U annual averages for inflation adjustment (SRC-08, BLS series CUUR0000SA0, period M13)."""
from datetime import datetime, timezone
import io
import json
from urllib.request import Request
from apps.area.http import default_opener
from apps.sources.snapshots import publish_snapshot, ValidationReport

SERIES = 'CUUR0000SA0'
URL = 'https://api.bls.gov/publicAPI/v1/timeseries/data/'
SCOPE = f'cpi-u:{SERIES}:annual'
ADAPTER_VERSION = 'bls-cpi-annual-v1'
LABEL = 'CPI-U, U.S. city average, annual average (BLS CUUR0000SA0)'


class CpiError(Exception):
    pass


def parse(raw, years):
    data = json.loads(raw)
    if data.get('status') != 'REQUEST_SUCCEEDED':
        raise CpiError('BLS request failed')
    series = data['Results']['series'][0]
    if series.get('seriesID') != SERIES:
        raise CpiError('Unexpected BLS series')
    values = {int(d['year']): float(d['value']) for d in series['data'] if d.get('period') == 'M13'}
    missing = [y for y in years if y not in values]
    if missing:
        raise CpiError(f'Annual averages missing for {missing}')
    return {str(y): values[y] for y in years}


def fetch(years, *, opener=None, timeout=30):
    body = json.dumps({'seriesid': [SERIES], 'startyear': str(min(years)), 'endyear': str(max(years)),
        'annualaverage': True}).encode()
    request = Request(URL, data=body, headers={'Content-Type': 'application/json',
        'User-Agent': 'ParagonRadar/0.1 (+https://github.com/AdiY10/Paragon.AI)'})
    with (opener or default_opener()).open(request, timeout=timeout) as response:
        raw = response.read(1_048_576)
    return parse(raw, years), datetime.now(timezone.utc)


def publish(values, retrieved_at, store):
    payload = json.dumps({'series': SERIES, 'annual_average': values}, sort_keys=True).encode()
    return publish_snapshot(source_id='SRC-08', scope=SCOPE, release='-'.join(sorted(values)),
        data_period=f'Annual averages {", ".join(sorted(values))}', source_url=URL,
        adapter_version=ADAPTER_VERSION, stream=io.BytesIO(payload), store=store, retrieved_at=retrieved_at,
        validation=ValidationReport(True, True, {'series': SERIES, 'period': 'M13'}, len(values)),
        context={'series': SERIES})


def load(snapshot, store):
    with store.open_verified(snapshot.artifact_key) as handle:
        return json.load(handle)['annual_average']
