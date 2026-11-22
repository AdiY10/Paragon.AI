"""Redesign B4a: bounded-memory ACS ingest, background ingest jobs, filtered LODES, cached probes, batched BLS."""
import io
import json
from pathlib import Path
import shutil
import pytest
from apps.area import economy as econ
from apps.area import jobs as lodes
from apps.demographics import acs

ACS_FIX = Path('tests/fixtures/real/ring_demographics')
AREA_FIX = Path('tests/fixtures/real/area')


def acs_lines(table):
    return open(ACS_FIX / f'acsdt5y2024-{table.lower()}.sample.dat')


# ---- ACS: national files once, bounded batches ---------------------------------

def test_batches_never_exceed_the_limit_and_big_states_go_alone():
    counts = {'06': 25_600, '48': 18_600, '09': 2_700, '36': 16_000, '01': 3_900, '02': 40_000}
    batches = acs.plan_batches(counts, 30_000)
    assert batches == [['01'], ['02'], ['06', '09'], ['36'], ['48']]
    assert sorted(s for b in batches for s in b) == sorted(counts)
    for batch in batches:
        assert len(batch) == 1 or sum(counts[s] for s in batch) <= 30_000
    assert acs.plan_batches({}, 10) == []


def test_count_block_groups_reads_only_block_group_rows():
    assert acs.count_block_groups(acs_lines('B01003')) == {'09': 3}


class RangeServer:
    """Serves bytes; honours Range unless told not to. Records requests."""
    def __init__(self, body, honour_range=True):
        self.body, self.honour, self.requests = body, honour_range, []

    def open(self, request, timeout=None):
        self.requests.append(request)
        rng = request.get_header('Range')
        if rng and self.honour:
            start = int(rng.split('=')[1].rstrip('-'))
            resp = io.BytesIO(self.body[start:])
            resp.status = 206
        else:
            resp = io.BytesIO(self.body)
            resp.status = 200
        return resp


def test_download_resumes_a_partial_file_and_restarts_when_range_is_ignored(tmp_path):
    body = b'GEO_ID|x\n' + b'1500000US091234567890|1\n' * 1000
    (tmp_path / 'b01003.dat.part').write_bytes(body[:100])
    server = RangeServer(body)
    paths = acs.download_tables(2024, tmp_path, opener=server, tables=['B01003'])
    assert paths['B01003'].read_bytes() == body and server.requests[0].get_header('Range') == 'bytes=100-'
    acs.download_tables(2024, tmp_path, opener=server, tables=['B01003'])
    assert len(server.requests) == 1  # already complete: no new request
    other = tmp_path / 'again'
    other.mkdir()
    (other / 'b01003.dat.part').write_bytes(b'garbage')
    acs.download_tables(2024, other, opener=RangeServer(body, honour_range=False), tables=['B01003'])
    assert (other / 'b01003.dat').read_bytes() == body


@pytest.mark.django_db
def test_all_states_ingest_parses_from_disk_in_batches_and_skips_existing(tmp_path, monkeypatch):
    from apps.sources.catalog import sync_catalog
    from apps.sources.storage import LocalArtifactStore
    from apps.demographics import service
    sync_catalog()
    cache = tmp_path / 'cache'
    cache.mkdir()
    for table in acs.TABLES:
        shutil.copy(ACS_FIX / f'acsdt5y2024-{table.lower()}.sample.dat', cache / f'{table.lower()}.dat')
    store = LocalArtifactStore(tmp_path / 'artifacts')
    seen = []
    real = service.ingest_acs
    monkeypatch.setattr(service, 'ingest_acs', lambda states, **kw: seen.append(states) or real(states, **kw))
    published = service.ingest_acs_all(2024, store=store, cache_dir=cache, opener=RangeServer(b''))
    assert seen == [['09']] and len(published) == 1  # only states present in the files
    rows = acs.load_rows(published[0][0], store)
    assert rows['091900435001']['B01003_001_E'] == 1103
    assert service.ingest_acs_all(2024, store=store, cache_dir=cache) == []  # already ingested


@pytest.mark.django_db
def test_a_missing_state_queues_one_background_ingest_and_the_analysis_waits(monkeypatch):
    from apps.demographics import service
    from apps.operations.models import JobRun
    job = service.queue_acs_ingest(2024, '36')
    assert job.kind == 'ingest_acs_state' and job.queue == 'paragon-maintenance'
    assert job.parameters == {'year': 2024, 'state': '36'} and job.dedup_key == 'acs:2024:36'
    assert service.queue_acs_ingest(2024, '36').pk == job.pk  # live: no duplicate
    assert service.queue_acs_ingest(2024, '3').dedup_key == 'acs:2024:3'  # prefixes never collide
    from django.utils import timezone
    JobRun.objects.filter(pk=job.pk).update(status='failed', finished_at=timezone.now())
    assert service.queue_acs_ingest(2024, '36') is None  # back off an hour after a failure
    JobRun.objects.filter(pk=job.pk).update(finished_at=timezone.now() - __import__('datetime').timedelta(hours=2))
    assert service.queue_acs_ingest(2024, '36').dedup_key == 'acs:2024:36:2'


@pytest.mark.django_db
def test_ingest_job_wakes_analyses_waiting_for_demographics(monkeypatch):
    from apps.operations.registry import ingest_acs_state
    from apps.operations.models import JobRun
    from backend.tests.test_signals import placed
    loc = placed()
    monkeypatch.setattr('apps.demographics.service.ingest_acs_all', lambda *a, **k: [('snap', True)])
    ctx = type('C', (), {'heartbeat': lambda self: None})()
    result = ingest_acs_state(ctx, {'year': 2024, 'state': '09'})
    assert result.records == 1 and result.detail == {'woken': 1}
    job = JobRun.objects.get(kind='analyze_location_bg')
    assert job.parameters['sections'] == ['demographics'] and job.scope == f'location:{loc.pk}'


# ---- LODES: stream, keep only the ring's blocks --------------------------------

def test_filtered_lodes_parse_equals_the_full_parse_restricted_to_the_ring():
    raw = (AREA_FIX / 'ct_wac_S000_JT00_2024.norwalk5mi.csv.gz').read_bytes()
    full = lodes.parse_wac(raw)
    keep = set(list(full)[::7]) | {'999999999999999'}
    assert lodes.parse_wac(raw, keep) == {g: v for g, v in full.items() if g in keep}


# ---- cached "newest release" probes --------------------------------------------

class HeadCounter:
    def __init__(self, published_year):
        self.year, self.calls = published_year, 0

    def open(self, request, timeout=None):
        self.calls += 1
        if f'_{self.year}.csv.gz' not in request.full_url:
            from urllib.error import HTTPError
            raise HTTPError(request.full_url, 404, 'nf', {}, None)
        resp = io.BytesIO(b'')
        resp.status = 200
        return resp


@pytest.mark.django_db
def test_lodes_year_probe_is_shared_and_not_a_citation(tmp_path):
    from apps.sources.catalog import sync_catalog
    from apps.sources.storage import LocalArtifactStore
    from apps.area.service import Run, latest_lodes_year
    sync_catalog()
    store = LocalArtifactStore(tmp_path)
    from datetime import date
    opener = HeadCounter(date.today().year - 2)
    run = Run(store, opener)
    assert latest_lodes_year(run, '09') == date.today().year - 2
    assert opener.calls == 2 and run.snapshots == [] and run.sources == {}
    again = Run(store, opener)  # another pin, another process: no probe requests
    assert latest_lodes_year(again, '09') == date.today().year - 2 and opener.calls == 2


# ---- BLS: batched LAUS --------------------------------------------------------

class BlsServer:
    def __init__(self):
        self.bodies = []

    def open(self, request, timeout=None):
        body = json.loads(request.data)
        self.bodies.append(body)
        series = [{'seriesID': s, 'data': [{'year': '2026', 'period': 'M09', 'value': '4.0', 'footnotes': []}]}
            for s in body['seriesid']]
        resp = io.BytesIO(json.dumps({'status': 'REQUEST_SUCCEEDED', 'Results': {'series': series}}).encode())
        resp.status = 200
        return resp


def test_laus_batches_respect_the_series_limit_and_split_per_county(monkeypatch):
    monkeypatch.delenv('BLS_API_KEY', raising=False)
    counties = [f'09{n:03d}' for n in range(1, 60, 2)] + ['36111', '36119']  # 30 CT + 2 NY counties
    server = BlsServer()
    out, url = econ.fetch_laus_many(counties, opener=server)
    assert url == econ.LAUS_V1 and [len(b['seriesid']) for b in server.bodies] == [25, 9]
    assert sum(len(b['seriesid']) for b in server.bodies) == 32 + 2  # state series fetched once each
    assert set(out) == set(counties)
    parsed = econ.parse_laus(out['36111'], '36111')
    assert parsed['rate'] == 0.04
    ids = {s['seriesID'] for s in json.loads(out['09029'])['Results']['series']}
    assert ids == {econ.laus_series('09029'), econ.state_laus_series('09029')}
    monkeypatch.setenv('BLS_API_KEY', 'test-key')
    server = BlsServer()
    out, url = econ.fetch_laus_many([f'{n:05d}' for n in range(1000, 1030)], opener=server)
    assert url == econ.LAUS_V2 and [len(b['seriesid']) for b in server.bodies] == [31]
