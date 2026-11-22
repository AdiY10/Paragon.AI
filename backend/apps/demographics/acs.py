"""ACS 5-year block-group estimates from the keyless table-based summary files (SRC-03).

The Census Data API now requires a key; the national bulk files do not
(docs/03 SRC-03). We stream each national table once, keep only block-group
rows for the requested states, and publish one immutable snapshot per state.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import re
from urllib.request import Request
from apps.area.http import default_opener
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
    response = (opener or default_opener()).open(request, timeout=timeout)
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
    if year == LEGACY_YEAR and line_source is None:
        return [extract_legacy_state(s, opener=opener, timeout=timeout) for s in sorted(set(states))]
    if year < 2021:
        raise AcsError('Only the 2024 table-based and 2019 sequence-based vintages are supported')
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


# ---- all-states ingest (redesign B4a) ------------------------------------------
# Each table-based file is national (every state, every geography level). Download it once to
# disk, then parse it from disk in batches of states, so memory stays bounded by the batch.

def download_tables(year, directory, *, opener=None, timeout=120, tables=None):
    """Stream each national table to ``directory`` once; an interrupted download resumes. {table: Path}."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    out = {}
    for table in (tables or TABLES):
        final = directory / f'{table.lower()}.dat'
        if not final.exists():
            part = directory / f'{table.lower()}.dat.part'
            have = part.stat().st_size if part.exists() else 0
            headers = dict(_HEADERS)
            if have:
                headers['Range'] = f'bytes={have}-'
            response = (opener or default_opener()).open(
                Request(BASE_URL.format(year=year, table=table.lower()), headers=headers), timeout=timeout)
            if response.status == 200:
                have, mode = 0, 'wb'   # the server ignored the range: start over
            elif response.status == 206 and have:
                mode = 'ab'
            else:
                raise AcsError(f'HTTP {response.status}')
            with open(part, mode) as handle:
                while chunk := response.read(1 << 20):
                    have += len(chunk)
                    if have > MAX_TABLE_BYTES:
                        raise AcsError('ACS table exceeds size limit')
                    handle.write(chunk)
            part.rename(final)
        out[table] = final
    return out


def file_lines(path):
    with open(path, encoding='utf-8', newline='') as handle:
        yield from handle


def count_block_groups(lines):
    """{state FIPS: block groups} from one national table file."""
    counts = {}
    start = len(BG_PREFIX)
    for line in lines:
        if line.startswith(BG_PREFIX):
            state = line[start:start + 2]
            counts[state] = counts.get(state, 0) + 1
    return counts


def plan_batches(counts, limit=30_000):
    """Group states (FIPS order) into batches of at most ``limit`` block groups; a bigger state goes alone."""
    batches, current, size = [], [], 0
    for state in sorted(counts):
        if current and size + counts[state] > limit:
            batches.append(current)
            current, size = [], 0
        current.append(state)
        size += counts[state]
    if current:
        batches.append(current)
    return batches


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


# ---- 2015-2019 vintage: legacy sequence-based summary files -----------------
# The trend baseline (docs/04 §4, MET-06/07) is ACS 2015-2019, which predates the
# table-based files. Each state publishes one zip of sequence files; we read only
# the members we need with HTTP range requests (about 1-2 MB per state, not the
# whole 50-500 MB zip). Layout from ACS_5yr_Seq_Table_Number_Lookup.txt (2019).
LEGACY_YEAR = 2019
LEGACY_BASE = 'https://www2.census.gov/programs-surveys/acs/summary_file/2019/data/5_year_by_state/'
LEGACY_LOOKUP_URL = 'https://www2.census.gov/programs-surveys/acs/summary_file/2019/documentation/user_tools/ACS_5yr_Seq_Table_Number_Lookup.txt'
# table -> (sequence, 1-based start column of the table's first cell, cells)
LEGACY_LAYOUT = {'B01003': ('0002', 130, 1), 'B11001': ('0035', 7, 9), 'B15003': ('0042', 125, 25),
    'B19001': ('0058', 7, 17), 'B19025': ('0058', 195, 1)}
STATE_FILES = {'01': ('Alabama', 'al'), '02': ('Alaska', 'ak'), '04': ('Arizona', 'az'), '05': ('Arkansas', 'ar'),
    '06': ('California', 'ca'), '08': ('Colorado', 'co'), '09': ('Connecticut', 'ct'), '10': ('Delaware', 'de'),
    '11': ('DistrictOfColumbia', 'dc'), '12': ('Florida', 'fl'), '13': ('Georgia', 'ga'), '15': ('Hawaii', 'hi'),
    '16': ('Idaho', 'id'), '17': ('Illinois', 'il'), '18': ('Indiana', 'in'), '19': ('Iowa', 'ia'), '20': ('Kansas', 'ks'),
    '21': ('Kentucky', 'ky'), '22': ('Louisiana', 'la'), '23': ('Maine', 'me'), '24': ('Maryland', 'md'),
    '25': ('Massachusetts', 'ma'), '26': ('Michigan', 'mi'), '27': ('Minnesota', 'mn'), '28': ('Mississippi', 'ms'),
    '29': ('Missouri', 'mo'), '30': ('Montana', 'mt'), '31': ('Nebraska', 'ne'), '32': ('Nevada', 'nv'),
    '33': ('NewHampshire', 'nh'), '34': ('NewJersey', 'nj'), '35': ('NewMexico', 'nm'), '36': ('NewYork', 'ny'),
    '37': ('NorthCarolina', 'nc'), '38': ('NorthDakota', 'nd'), '39': ('Ohio', 'oh'), '40': ('Oklahoma', 'ok'),
    '41': ('Oregon', 'or'), '42': ('Pennsylvania', 'pa'), '44': ('RhodeIsland', 'ri'), '45': ('SouthCarolina', 'sc'),
    '46': ('SouthDakota', 'sd'), '47': ('Tennessee', 'tn'), '48': ('Texas', 'tx'), '49': ('Utah', 'ut'),
    '50': ('Vermont', 'vt'), '51': ('Virginia', 'va'), '53': ('Washington', 'wa'), '54': ('WestVirginia', 'wv'),
    '55': ('Wisconsin', 'wi'), '56': ('Wyoming', 'wy')}


def check_legacy_layout(lookup_lines):
    """Verify LEGACY_LAYOUT against the official lookup file (used by tests and ingestion)."""
    import csv
    found = {}
    for row in csv.reader(lookup_lines):
        if len(row) > 5 and row[1] in LEGACY_LAYOUT and row[4].strip() and row[3].strip() == '':
            found[row[1]] = (row[2], int(row[4]), int(row[5].split()[0]))
    if found != LEGACY_LAYOUT:
        raise AcsError(f'2019 sequence layout differs from the official lookup: {found}')


class HttpRangeFile:
    """Minimal seekable file over HTTP range requests, enough for zipfile."""
    def __init__(self, url, opener=None, timeout=60):
        self.url, self.opener, self.timeout, self.pos = url, opener or default_opener(), timeout, 0
        with self.opener.open(Request(url, method='HEAD', headers=_HEADERS), timeout=timeout) as r:
            self.size = int(r.headers['Content-Length'])
        self.requests = 0

    def seekable(self):
        return True

    def tell(self):
        return self.pos

    def seek(self, offset, whence=0):
        self.pos = {0: offset, 1: self.pos + offset, 2: self.size + offset}[whence]
        return self.pos

    def read(self, n=-1):
        if n is None or n < 0:
            n = self.size - self.pos
        if n == 0 or self.pos >= self.size:
            return b''
        if n > MAX_TABLE_BYTES:
            raise AcsError('Range read exceeds size limit')
        end = min(self.size, self.pos + n) - 1
        req = Request(self.url, headers={**_HEADERS, 'Range': f'bytes={self.pos}-{end}'})
        with self.opener.open(req, timeout=self.timeout) as r:
            if r.status != 206:
                raise AcsError('Server ignored the range request')
            data = r.read(end - self.pos + 2)
        self.requests += 1
        self.pos += len(data)
        return data


_HEADERS = {'User-Agent': 'ParagonRadar/0.1 (+https://github.com/AdiY10/Paragon.AI)'}


def parse_legacy(state, geo_csv, sequences):
    """Build block-group rows from the 2019 geography file and sequence (e, m) files.

    ``sequences`` maps sequence number -> (estimate text, MOE text).
    """
    import csv
    logrec = {}
    for row in csv.reader(io.StringIO(geo_csv)):
        if len(row) < 49 or row[2] != '150':
            continue
        geoid = row[48]
        if not geoid.startswith('15000US') or len(geoid) != 19:
            raise AcsError('Unexpected 2019 geography record')
        logrec[row[4]] = geoid[7:]
    if not logrec:
        raise AcsError('No block groups in 2019 geography file')
    rows = {g: {} for g in logrec.values()}
    for table, (seq, start, cells) in LEGACY_LAYOUT.items():
        est_text, moe_text = sequences[seq]
        for text, kind in ((est_text, 'E'), (moe_text, 'M')):
            for line in text.splitlines():
                parts = line.split(',')
                if len(parts) < start - 1 + cells or parts[4] != seq:
                    raise AcsError(f'Malformed 2019 sequence {seq} row')
                geoid = logrec.get(parts[5])
                if geoid is None:
                    continue
                for cell in TABLES[table]:
                    raw = parts[start - 2 + int(cell)]
                    rows[geoid][f'{table}_{cell}_{kind}'] = parse_value(raw, moe=kind == 'M')
    keys = [f'{t}_{c}_{k}' for t, cells in TABLES.items() for c in cells for k in ('E', 'M')]
    for values in rows.values():
        for key in keys:
            values.setdefault(key, None)
    return AcsExtract(LEGACY_YEAR, state, rows, (), datetime.now(timezone.utc))


def extract_legacy_state(state, *, opener=None, timeout=60):
    import zipfile
    if state not in STATE_FILES:
        raise AcsError(f'Unsupported state {state}')
    name, abbr = STATE_FILES[state]
    url = f'{LEGACY_BASE}{name}_Tracts_Block_Groups_Only.zip'
    archive = zipfile.ZipFile(HttpRangeFile(url, opener, timeout))
    geo = archive.read(f'g{LEGACY_YEAR}5{abbr}.csv').decode('latin-1')
    sequences = {}
    for seq in sorted({v[0] for v in LEGACY_LAYOUT.values()}):
        sequences[seq] = tuple(archive.read(f'{k}{LEGACY_YEAR}5{abbr}{seq}000.txt').decode('latin-1') for k in 'em')
    extract = parse_legacy(state, geo, sequences)
    return AcsExtract(extract.year, state, extract.rows, (url,), extract.retrieved_at)
