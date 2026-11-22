"""R2 item 4: queue routing, lease renewal, recovery fencing, maintenance and the supervisor."""
import importlib.util
from datetime import timedelta
from pathlib import Path
import uuid
import pytest
from django.conf import settings
from django.utils import timezone
from apps.operations import registry, runner
from apps.operations.contracts import JobResult, JobFailure
from apps.operations.models import JobRun

pytestmark = pytest.mark.django_db


def test_user_triggered_work_runs_on_the_foreground_cluster():
    fg = {k for k, s in registry.REGISTRY.items() if s.queue == 'paragon-foreground'}
    assert fg == {'compute_area_profile', 'compute_ring_demographics', 'brief_weekly', 'analyze_location'}
    clusters = {settings.Q_CLUSTER['name']: settings.Q_CLUSTER, **settings.Q_CLUSTER['ALT_CLUSTERS']}
    for spec in registry.REGISTRY.values():
        cluster = clusters[spec.queue]
        assert spec.timeout_seconds <= cluster['timeout'] < cluster['retry']


def test_heartbeat_renews_lease_and_fenced_attempts_stop(monkeypatch):
    spec = registry.REGISTRY['flood_recheck']
    seen = {}

    def handler(ctx, params):
        job = JobRun.objects.get(pk=ctx.job_id)
        seen['initial'] = job.lease_expires_at - job.started_at
        ctx.heartbeat()
        seen['renewed'] = JobRun.objects.get(pk=ctx.job_id).lease_expires_at
        JobRun.objects.filter(pk=ctx.job_id).update(attempt_token=uuid.uuid4())  # recovery fenced us
        ctx.heartbeat()
        return JobResult(records=1)
    monkeypatch.setitem(registry.REGISTRY, 'flood_recheck', registry.JobSpec(handler, spec.queue, spec.timeout_seconds))
    job = JobRun.objects.create(kind='flood_recheck', scope='global', dedup_key='x', queue=spec.queue)
    with pytest.raises(Exception):
        runner.execute_job(str(job.pk))
    assert seen['initial'] == timedelta(seconds=600)
    assert seen['renewed'] > timezone.now() + timedelta(seconds=590)


def test_maintenance_daily_expires_old_records():
    from apps.operations.models import AlertEvent
    old = timezone.now() - timedelta(days=200)
    JobRun.objects.create(kind='flood_recheck', scope='global', dedup_key='old', queue='paragon-maintenance',
        status='succeeded', finished_at=old)
    AlertEvent.objects.create(key='k', summary='s', first_at=old, last_at=old, resolved_at=old)
    ctx = type('C', (), {'heartbeat': lambda self: None})()
    result = registry.maintenance_daily(ctx, {})
    assert result.records == 2 and not AlertEvent.objects.exists()


def test_overture_scans_are_serialized(monkeypatch):
    import threading
    from apps.area import locks
    order = []

    def work(n):
        with locks.overture_capture_lock():
            order.append(('start', n))
            threading.Event().wait(0.05)
            order.append(('end', n))
    threads = [threading.Thread(target=work, args=(n,)) for n in range(2)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert [o[0] for o in order] == ['start', 'end', 'start', 'end']


def test_supervisor_starts_both_clusters_and_scheduler():
    path = Path(__file__).resolve().parents[2] / 'infra' / 'start_all.py'
    spec = importlib.util.spec_from_file_location('start_all', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # importing must not start anything
    assert len(mod.build_commands({})) == 1
    cmds = mod.build_commands({'RUN_BACKGROUND_WORKERS': 'true'})
    assert [extra.get('Q_CLUSTER_NAME') for argv, extra in cmds if 'qcluster' in argv] == [None, 'paragon-foreground']
    assert any('run_scheduler' in argv for argv, _ in cmds)
