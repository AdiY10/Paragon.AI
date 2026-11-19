"""ACS 5-year block-group estimates from the keyless table-based summary files (SRC-03).

The Census Data API now requires a key; the national bulk files do not
(docs/03 SRC-03). We stream each national table once, keep only block-group
rows for the requested states, and publish one immutable snapshot per state.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
import io
import json
import re
from urllib.request import Request, build_opener
from apps.sources.snapshots import publish_snapshot, ValidationReport

ADAPTER_VERSION = 'acs-table-sf-v1'
BASE_URL = 'https://www2.census.gov/programs-surveys/acs/summary_file/{year}/table-based-SF/data/5YRData/acsdt5y{year}-{table}.dat'
# Tables and the cells each metric needs (docs/04 §4, MET-01..05).
TABLES = {
    'B01003': ['001'],
    'B11001': ['001'],
    'B19001': [f'{i:03d}' for i in range(1, 18)],
    'B19025': ['001'],
    'B15003': ['001', '022', '023', '024', '025'],
}
BG_PREFIX = '1500000US'
MAX_TABLE_BYTES = 400 * 1024 * 1024
CONTROLLED_MOE = -555555555   # "estimate is controlled": no sampling error
STATE = re.compile(r'^\d{2}$')


class AcsError(Exception):
    pass


def vintage_period(year):
    return f'ACS {year - 4}–{year} 5-year'


def parse_value(raw, *, moe=False):
    """Return a number, or None for ACS jam values. Controlled MOEs become 0."""
    raw = raw.strip()
    if raw in ('', '.', 'null', 'N'):
        return None
    try:
        value = float(raw)
    except ValueError:
        raise AcsError(f'Non-numeric ACS value {raw!r}') from None
    if moe and value == CONTROLLED_MOE:
        return 0.0
    if value < 0:
        return None
    return value


def parse_table(lines, table, states):
    """Yield (block-group GEOID, {cell_E/M: value}) for block groups in ``states``."""
    states = set(states)
    header = next(lines, None)
    if header is None:
        raise AcsError(f'{table}: empty file')
    columns = header.rstrip('\r\n').split('|')
    if columns[0] != 'GEO_ID':
        raise AcsError(f'{table}: unexpected header')
    wanted = {}
    for cell in TABLES[table]:
        for kind in ('E', 'M'):
            name = f'{table}_{kind}{cell}'
            if name not in columns:
                raise AcsError(f'{table}: missing column {name}')
            wanted[columns.index(name)] = (f'{table}_{cell}_{kind}', kind == 'M')
    prefixes = tuple(BG_PREFIX + s for s in states)
    for line in lines:
        if not line.startswith(prefixes):
            continue
        parts = line.rstrip('\r\n').split('|')
        if len(parts) != len(columns):
            raise AcsError(f'{table}: malformed row')
        geoid = parts[0][len(BG_PREFIX):]
        if not re.fullmatch(r'\d{12}', geoid):
            raise AcsError(f'{table}: invalid block-group GEOID')
        yield geoid, {key: parse_value(parts[i], moe=is_moe) for i, (key, is_moe) in wanted.items()}


def _stream_lines(url, opener, timeout):
    request = Request(url, headers={'User-Agent': 'ParagonRadar/0.1 (+https://github.com/AdiY10/Paragon.AI)'})
    response = (opener or build_opener()).open(request, timeout=timeout)
    if response.status != 200:
        raise AcsError(f'HTTP {response.status}')
    read = 0
    for raw in response:
        read += len(raw)
        if read > MAX_TABLE_BYTES:
            raise AcsError('ACS table exceeds size limit')
        yield raw.decode('utf-8')


@dataclass(frozen=True)
class AcsExtract:
    year: int
    state: str
    rows: dict          # GEOID -> {cell: value}
    source_urls: tuple
    retrieved_at: datetime

    def payload(self):
        return json.dumps({'year': self.year, 'state': self.state, 'tables': TABLES,
            'rows': self.rows}, sort_keys=True, separators=(',', ':')).encode()


def extract_states(year, states, *, opener=None, timeout=120, line_source=None):
    """Download each table once and split block-group rows by state."""
    if year < 2021:
        raise AcsError('Table-based summary files start with the 2021 vintage')
    states = sorted(set(states))
    if not states or not all(STATE.fullmatch(s) for s in states):
        raise AcsError('States must be two-digit FIPS codes')
    rows = {s: {} for s in states}
    urls = []
    for table in TABLES:
        url = BASE_URL.format(year=year, table=table.lower())
        urls.append(url)
        lines = line_source(table) if line_source else _stream_lines(url, opener, timeout)
        seen = 0
        for geoid, values in parse_table(iter(lines), table, states):
            rows[geoid[:2]].setdefault(geoid, {}).update(values)
            seen += 1
        if seen == 0:
            raise AcsError(f'{table}: no block groups for {states}')
    retrieved = datetime.now(timezone.utc)
    # Census omits some block groups from some tables (e.g. B19025 where too few
    # households to publish). Absent cells become None, i.e. "not published",
    # never zero; metrics decide how to handle them.
    keys = [f'{t}_{c}_{k}' for t, cells in TABLES.items() for c in cells for k in ('E', 'M')]
    for state_rows in rows.values():
        for values in state_rows.values():
            for key in keys:
                values.setdefault(key, None)
    return [AcsExtract(year, s, rows[s], tuple(urls), retrieved) for s in states]


def scope_for(year, state):
    return f'acs5:{year}:bg:{state}'


def publish_extract(extract, store):
    payload = extract.payload()
    return publish_snapshot(source_id='SRC-03', scope=scope_for(extract.year, extract.state),
        release=str(extract.year), data_period=vintage_period(extract.year),
        source_url=extract.source_urls[0].rsplit('/', 1)[0] + '/', adapter_version=ADAPTER_VERSION,
        stream=io.BytesIO(payload), store=store, retrieved_at=extract.retrieved_at,
        validation=ValidationReport(True, True, {'tables': TABLES}, len(extract.rows)),
        context={'tables': sorted(TABLES), 'geography': 'block group', 'state': extract.state})


def load_rows(snapshot, store):
    with store.open_verified(snapshot.artifact_key) as handle:
        data = json.load(handle)
    return data['rows']
