"""R2 item 1: failure accounting, operational alerts and logging without location details."""
import logging
import pytest
from django.utils import timezone
from apps.operations.alerts import raise_alert, resolve_alert, open_alerts
from apps.operations.contracts import JobResult, JobFailure
from apps.operations.models import AlertEvent, JobRun
from apps.operations import registry, runner

pytestmark = pytest.mark.django_db


def queued(kind):
    from apps.operations.registry import REGISTRY
    import uuid
    return JobRun.objects.create(kind=kind, scope='global', dedup_key=str(uuid.uuid4()), queue=REGISTRY[kind].queue)


def test_alert_dedupes_counts_and_reopens_after_resolution():
    a = raise_alert('job:x:failing', 'x failed twice')
    b = raise_alert('job:x:failing', 'x failed twice')
    assert a.pk == b.pk and AlertEvent.objects.get().count == 2
    resolve_alert('job:x:failing')
    assert not open_alerts().exists()
    raise_alert('job:x:failing', 'x failed again')
    assert AlertEvent.objects.get().count == 1 and open_alerts().count() == 1


def test_partial_failures_are_recorded_and_alerted(monkeypatch):
    spec = registry.REGISTRY['flood_recheck']
    monkeypatch.setitem(registry.REGISTRY, 'flood_recheck', registry.JobSpec(
        lambda ctx, params: JobResult(records=3, failed=2, detail={'loc-a': 'TIMEOUT', 'loc-b': 'SOURCE_ERROR'}),
        spec.queue, spec.timeout_seconds))
    job = queued('flood_recheck')
    runner.execute_job(str(job.pk))
    job.refresh_from_db()
    assert (job.status, job.records, job.failed_items) == ('succeeded', 3, 2)
    assert job.detail == {'loc-a': 'TIMEOUT', 'loc-b': 'SOURCE_ERROR'}
    assert AlertEvent.objects.get(key='job:flood_recheck:partial').summary.startswith('flood recheck: 2 of 5')


def test_two_consecutive_terminal_failures_raise_then_success_resolves(monkeypatch):
    spec = registry.REGISTRY['flood_recheck']

    def boom(ctx, params):
        raise JobFailure('SOURCE_ERROR', retryable=False)
    monkeypatch.setitem(registry.REGISTRY, 'flood_recheck', registry.JobSpec(boom, spec.queue, spec.timeout_seconds))
    runner.execute_job(str(queued('flood_recheck').pk))
    assert not AlertEvent.objects.filter(key='job:flood_recheck:failing').exists()
    runner.execute_job(str(queued('flood_recheck').pk))
    assert open_alerts().filter(key='job:flood_recheck:failing').exists()
    monkeypatch.setitem(registry.REGISTRY, 'flood_recheck', registry.JobSpec(
        lambda ctx, params: JobResult(records=1), spec.queue, spec.timeout_seconds))
    runner.execute_job(str(queued('flood_recheck').pk))
    assert not open_alerts().filter(key='job:flood_recheck:failing').exists()


def test_refresh_where_every_location_fails_is_a_terminal_failure(monkeypatch):
    from apps.area import refresh
    monkeypatch.setattr(refresh, 'refresh_hazards', lambda ctx: refresh.Outcome(done=0, failed=3, failures={'a': 'X'}))
    with pytest.raises(JobFailure):
        registry.flood_recheck(type('C', (), {'heartbeat': lambda self: None})(), {})


def test_source_alert_after_two_failures_without_scope_details():
    from apps.sources.catalog import sync_catalog
    from apps.sources.health import record_check
    sync_catalog()
    scope = 'hpms:41.126611,-73.388299'
    record_check(source_id='SRC-10', scope=scope, run_key='r1', succeeded=False, error_code='TIMEOUT')
    assert not open_alerts().exists()
    record_check(source_id='SRC-10', scope=scope, run_key='r2', succeeded=False, error_code='TIMEOUT')
    alert = open_alerts().get()
    assert '41.12' not in alert.key + alert.summary and 'TIMEOUT' in alert.summary
    record_check(source_id='SRC-10', scope=scope, run_key='r3', succeeded=True)
    assert not open_alerts().exists()


def test_refresh_failures_logged_with_ids_not_coordinates(monkeypatch, caplog):
    from apps.area import refresh
    from apps.area.http import SourceError
    from backend.tests.test_refresh import locations, Ctx
    locations()
    monkeypatch.setattr('apps.area.service.compute_area', lambda *a, **k: (_ for _ in ()).throw(SourceError('TIMEOUT')))
    with caplog.at_level(logging.WARNING, logger='apps'):
        out = refresh.refresh_economy(Ctx())
    assert out.failed == 2 and set(out.failures.values()) == {'TIMEOUT'}
    text = caplog.text
    assert 'refresh economy failed for location' in text and '41.1' not in text and '-73.4' not in text


def test_acs_rollover_is_held_until_enabled(monkeypatch, settings):
    from apps.area import refresh
    from backend.tests.test_refresh import locations, Ctx
    locations()
    settings.ACS_ROLLOVER_ENABLED = False
    ingested = []
    monkeypatch.setattr(refresh, 'newest_acs_year', lambda opener=None: 2025)
    monkeypatch.setattr(refresh, 'ingested_acs_states', lambda year: set() if year == 2025 else {'09', '36'})
    monkeypatch.setattr('apps.demographics.service.ingest_acs', lambda states, year, **k: ingested.append(year))
    monkeypatch.setattr('apps.area.service.compute_area', lambda *a, **k: [])
    out = refresh.refresh_annual(Ctx())
    assert 2025 not in ingested and out.info['acs_rollover_pending'] == 2025


def test_alerts_api_is_admin_only(client):
    from backend.tests.test_accounts import member
    raise_alert('job:x:failing', 'x failed twice')
    user, _ = member('m@example.org', 'member')
    client.force_login(user)
    assert client.get('/api/admin/alerts/').status_code == 403
    admin, _ = member('a@example.org', 'admin')
    client.force_login(admin)
    body = client.get('/api/admin/alerts/').json()
    assert body['open'][0]['summary'] == 'x failed twice'
