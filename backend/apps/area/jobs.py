"""Jobs located in each ring from LEHD LODES 8 workplace files (SRC-05; MET-08, MET-09).

LODES counts jobs by workplace census block (2020 blocks), with noise added at
block level for confidentiality, so values are only ever shown summed over a
ring. Connecticut LODES blocks keep legacy county codes, which is exactly what
the 2020 TIGERweb blocks use, so blocks join by GEOID (docs/03 SRC-05).
"""
import csv
from datetime import date
import gzip
import io
from urllib.request import Request
from apps.demographics.rings import haversine_miles
from .http import SourceError, default_opener, fetch
from .traffic_hazards import STATES

URL = 'https://lehd.ces.census.gov/data/lodes/LODES8/{st}/wac/{st}_wac_S000_JT00_{year}.csv.gz'
COLUMNS = {'C000': 'total', 'CNS07': 'retail', 'CNS18': 'food_service'}
MIN_JOBS_FOR_TREND = 1000  # docs/04 MET-09


def url_for(state_fips, year):
    st = STATES.get(state_fips)
    if st is None:
        raise SourceError('NOT_COVERED', 'unsupported state')
    return URL.format(st=st.lower(), year=year)


def published(state_fips, year, *, opener=None):
    try:
        with (opener or default_opener()).open(Request(url_for(state_fips, year), method='HEAD'), timeout=20) as r:
            return r.status == 200
    except Exception:
        return False


def latest_year(state_fips, *, today=None, opener=None):
    year = (today or date.today()).year
    for candidate in range(year - 1, year - 6, -1):
        if published(state_fips, candidate, opener=opener):
            return candidate
    raise SourceError('NOT_COVERED', 'no LODES year published for this state')


def fetch_wac(state_fips, year, *, opener=None):
    url = url_for(state_fips, year)
    return fetch(url, opener=opener, max_bytes=64 * 1024 * 1024, timeout=60), url


def parse_wac(raw_gz, keep=None):
    """block GEOID -> (total, retail, food_service), streamed; only blocks in ``keep`` when given.

    Streaming with a filter keeps a large state (California: ~600k workplace blocks) from being
    held in memory just to read the few thousand blocks inside one property's rings (B4a).
    """
    try:
        reader = csv.reader(io.TextIOWrapper(gzip.GzipFile(fileobj=io.BytesIO(raw_gz)), encoding='utf-8', newline=''))
        header = next(reader)
        if not {'w_geocode', *COLUMNS} <= set(header):
            raise SourceError('SCHEMA_ERROR', 'unexpected LODES columns')
        at = header.index('w_geocode')
        columns = [header.index(c) for c in COLUMNS]
        out = {}
        for row in reader:
            geoid = row[at]
            if keep is not None and geoid not in keep:
                continue
            if len(geoid) != 15 or not geoid.isdigit():
                raise SourceError('SCHEMA_ERROR', 'invalid workplace block')
            out[geoid] = tuple(int(row[i]) for i in columns)
        return out
    except (OSError, EOFError, UnicodeDecodeError, StopIteration, ValueError, IndexError):
        raise SourceError('SCHEMA_ERROR', 'not a LODES gzip file') from None


def ring_jobs(blocks, wac, center, radii):
    """Sum jobs of 2020 blocks whose internal point is inside each ring."""
    lat0, lon0 = center
    distances = [(b.geoid, haversine_miles(lat0, lon0, b.lat, b.lon)) for b in blocks]
    out = {}
    for r in radii:
        sums = [0, 0, 0]
        workplaces = 0
        for geoid, d in distances:
            if d <= r and geoid in wac:
                workplaces += 1
                for i, v in enumerate(wac[geoid]):
                    sums[i] += v
        out[r] = {'total': sums[0], 'retail': sums[1], 'food_service': sums[2], 'workplace_blocks': workplaces}
    return out


def with_trend(current, prior):
    """MET-09: year-over-year change, only when both years have at least 1,000 jobs."""
    result = dict(current)
    if prior is None:
        return {**result, 'prior_total': None, 'change_pct': None, 'change_reason': 'NOT_ENOUGH_DATA'}
    result['prior_total'] = prior['total']
    if current['total'] < MIN_JOBS_FOR_TREND or prior['total'] < MIN_JOBS_FOR_TREND:
        return {**result, 'change_pct': None, 'change_reason': 'NOT_ENOUGH_DATA'}
    return {**result, 'change_pct': (current['total'] - prior['total']) / prior['total'], 'change_reason': None}
