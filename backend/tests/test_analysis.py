"""Redesign B3a: automatic analysis (ensure, run, sweep, hooks, heartbeat fencing)."""
from datetime import timedelta
import uuid
import pytest
from django.utils import timezone
from apps.area import analysis
from apps.locations.models import Location
from apps.operations.models import AlertEvent, JobRun
from backend.tests.test_signals import placed, section

pytestmark = pytest.mark.django_db
ALL = ['hazards', 'traffic', 'economy', 'businesses', 'jobs', 'demographics']


def finish(job, status='failed', at=None):
    JobRun.objects.filter(pk=job.pk).update(status=status, finished_at=at or timezone.now())


def test_missing_sections_cover_absent_retryable_and_outdated_results():
    loc = placed()
    assert analysis.missing_sections(loc) == ALL
    section(loc, 'economy', {})
    section(loc, 'traffic', {'reason': 'NOT_COVERED'}, status='unavailable')   # an answer, not a failure
    section(loc, 'hazards', {'reason': 'HTTP_ERROR'}, status='unavailable')    # transient: retry
    section(loc, 'jobs', {})
    from apps.area.models import AreaSection
    AreaSection.objects.create(location=loc, revision=loc.current_revision, analysis_version=loc.analysis_version,
        section='businesses', status='available', data={}, sources=[], snapshot_ids=[],
        inputs_sha256=uuid.uuid4().hex, logic_version=1)  # older than SECTION_LOGIC['businesses']
    assert analysis.missing_sections(loc) == ['hazards', 'businesses', 'demographics']


def test_ensure_returns_the_live_job_and_numbers_new_attempts():
    loc = placed()
    first = analysis.ensure_analysis(loc.pk)
    assert first.kind == 'analyze_location' and first.dedup_key == f'analyze:{loc.pk}:{loc.analysis_version}:1'
    assert first.parameters == {'location_id': str(loc.pk), 'analysis_version': loc.analysis_version, 'sections': ALL}
    assert analysis.ensure_analysis(loc.pk).pk == first.pk  # live: no second job
    finish(first)
    second = analysis.ensure_analysis(loc.pk, interactive=False)
    assert second.kind == 'analyze_location_bg' and second.dedup_key.endswith(':2')
    # Explicit sections are recomputed even when present; unknown names are refused.
    finish(second, 'succeeded')
    assert analysis.ensure_analysis(loc.pk, ['demographics']).parameters['sections'] == ['demographics']
    with pytest.raises(ValueError):
        analysis.ensure_analysis(loc.pk, ['visits'])


def test_ensure_skips_unplaced_archived_and_complete_locations(monkeypatch):
    from apps.locations.service import create_location
    unplaced = create_location(name='No pin', address='2 Main St', actor=None)
    assert analysis.ensure_analysis(unplaced.pk) is None
    archived = placed('Old')
    Location.objects.filter(pk=archived.pk).update(status='archived')
    assert analysis.ensure_analysis(archived.pk) is None
    done = placed('Done')
    monkeypatch.setattr(analysis, 'missing_sections', lambda location: [])
    assert analysis.ensure_analysis(done.pk) is None
    assert not JobRun.objects.exists()


def test_three_failures_in_a_day_stop_retries_until_the_window_passes():
    loc = placed()
    now = timezone.now()
    for _ in range(3):
        finish(analysis.ensure_analysis(loc.pk, now=now), at=now)
    assert analysis.ensure_analysis(loc.pk, now=now) is None
    assert analysis.ensure_analysis(loc.pk, now=now + timedelta(hours=25)).dedup_key.endswith(':4')


def test_location_changes_queue_the_analysis_after_commit(settings, django_capture_on_commit_callbacks):
    from django.contrib.auth import get_user_model
    from apps.locations.service import create_location, change_pin, update_location
    settings.AUTO_ANALYZE = True
    user = get_user_model().objects.create_user(username='a@example.org', email='a@example.org')
    with django_capture_on_commit_callbacks(execute=False) as callbacks:
        loc = create_location(name='Seed', address='1 Main', lat=41.1, lon=-73.4, pin_method='manual', actor=None)
    assert not JobRun.objects.exists()  # nothing before commit
    for callback in callbacks:
        callback()
    seed_job = JobRun.objects.get()
    assert seed_job.kind == 'analyze_location_bg'  # no actor: bulk/seed work stays in the background
    with django_capture_on_commit_callbacks(execute=True):
        loc = change_pin(location_id=loc.pk, expected_version=loc.version, lat=41.2, lon=-73.5, actor=user)
    job = JobRun.objects.get(kind='analyze_location')
    assert job.parameters['analysis_version'] == loc.analysis_version and job.requested_by == user
    with django_capture_on_commit_callbacks(execute=True):
        loc = update_location(location_id=loc.pk, expected_version=loc.version, attributes={'ring_preset': '3/5/10'}, actor=user)
    assert JobRun.objects.filter(parameters__analysis_version=loc.analysis_version).count() == 1
    with django_capture_on_commit_callbacks(execute=True):  # address change unplaces: nothing to analyze
        loc = update_location(location_id=loc.pk, expected_version=loc.version, attributes={'address': '9 Elm'}, actor=user)
    assert JobRun.objects.count() == 3


def test_hooks_are_off_when_auto_analyze_is_disabled(django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        placed()
    assert not JobRun.objects.exists()


def fake_sections(monkeypatch, on_section=None):
    calls = []

    def compute_section(location, revision, version, name, **kw):
        calls.append(name)
        if on_section:
            on_section(location, name)
        return section(location, name, {'reason': 'HTTP_ERROR'} if name == 'traffic' else {},
            status='unavailable' if name == 'traffic' else 'available')

    def compute_for_location(location_id, **kw):
        calls.append('demographics')
        from apps.demographics.service import DemographicsUnavailable
        raise DemographicsUnavailable('NOT_COVERED', 'state not ingested')
    monkeypatch.setattr('apps.area.service.compute_section', compute_section)
    monkeypatch.setattr('apps.demographics.service.compute_for_location', compute_for_location)
    evaluated = []
    monkeypatch.setattr('apps.insights.signals.safe_evaluate', lambda pk: evaluated.append(pk))
    return calls, evaluated


def test_job_runs_sections_in_order_and_evaluates_alerts_once(monkeypatch, tmp_path, settings):
    from apps.operations.runner import execute_job
    settings.SOURCE_ARTIFACT_ROOT = tmp_path
    calls, evaluated = fake_sections(monkeypatch)
    loc = placed()
    job = analysis.ensure_analysis(loc.pk)
    execute_job(str(job.pk))
    job.refresh_from_db()
    assert calls == ALL and evaluated == [str(loc.pk)]
    assert job.status == 'succeeded' and job.records == 4
    assert job.failed_items == 1  # only the transient traffic failure counts; NOT_COVERED is an answer
    assert job.detail == {'traffic': 'HTTP_ERROR', 'demographics': 'NOT_COVERED'}


def test_pin_moved_mid_run_stops_as_stale(monkeypatch, tmp_path, settings):
    from apps.operations.runner import execute_job
    settings.SOURCE_ARTIFACT_ROOT = tmp_path

    def move(location, name):
        if name == 'hazards':
            Location.objects.filter(pk=location.pk).update(analysis_version=location.analysis_version + 1)
    calls, evaluated = fake_sections(monkeypatch, move)
    loc = placed()
    job = analysis.ensure_analysis(loc.pk)
    execute_job(str(job.pk))
    job.refresh_from_db()
    assert calls == ['hazards'] and evaluated == []
    assert job.status == 'succeeded' and job.detail == {'stale': 'STALE'}


def test_heartbeat_check_stops_a_fenced_attempt():
    from apps.operations.contracts import JobFailure
    from apps.operations.runner import JobContext
    loc = placed()
    job = analysis.ensure_analysis(loc.pk)
    token = uuid.uuid4()
    JobRun.objects.filter(pk=job.pk).update(status='running', attempt_token=token)
    beat = analysis.Heartbeat(JobContext(job.pk, token, 300), every=3600)
    with beat:
        beat.check()  # our lease: renews
        assert JobRun.objects.get(pk=job.pk).lease_expires_at is not None
        JobRun.objects.filter(pk=job.pk).update(attempt_token=uuid.uuid4())  # recovery took the job over
        with pytest.raises(JobFailure):
            beat.check()
    beat.fenced = True
    with pytest.raises(JobFailure):
        beat.check()


def test_sweep_queues_background_work_with_a_cap_and_backoff():
    a, b, c = placed('A'), placed('B'), placed('C')
    now = timezone.now()
    assert analysis.sweep(now=now, limit=2) == {'queued': 2}
    live = list(JobRun.objects.filter(kind='analyze_location_bg'))
    assert len(live) == 2
    assert analysis.sweep(now=now, limit=2) == {'queued': 0}  # cap: two live background analyses
    for job in live:
        finish(job, 'succeeded', at=now)  # sections still missing (fake): retry only after backoff
    assert analysis.sweep(now=now + timedelta(minutes=1), limit=2) == {'queued': 1}  # C, never tried
    finish(JobRun.objects.get(status='queued'), 'succeeded', at=now)
    assert analysis.sweep(now=now + timedelta(minutes=5), limit=5) == {'queued': 0}
    assert analysis.sweep(now=now + timedelta(minutes=11), limit=5) == {'queued': 3}


def test_sweep_skips_candidates_after_owned_and_alerts_on_unplaced_owned():
    from apps.locations.service import create_location
    owned = placed('Owned')
    placed('Candidate', status='candidate')
    nopin = create_location(name='Pinless Plaza', address='3 Main', actor=None, status='owned')
    analysis.sweep(limit=1)
    assert JobRun.objects.get().scope == f'location:{owned.pk}'
    alert = AlertEvent.objects.get(key=f'location:{nopin.pk}:unplaced')
    assert 'Pinless Plaza' in alert.summary and '3 Main' not in alert.summary
    analysis.sweep(limit=1)
    assert AlertEvent.objects.get(key=alert.key).count == 1  # not re-raised every tick
    from apps.locations.service import change_pin
    change_pin(location_id=nopin.pk, expected_version=nopin.version, lat=41.0, lon=-73.0, actor=None)
    analysis.sweep(limit=1)
    assert AlertEvent.objects.get(key=alert.key).resolved_at is not None


def test_scheduler_sweeps_at_most_every_five_minutes(settings, monkeypatch):
    from apps.operations import scheduler
    settings.AUTO_ANALYZE = True
    runs = []
    monkeypatch.setattr(analysis, 'sweep', lambda now: runs.append(now) or {'queued': 0})
    monkeypatch.setattr(scheduler, '_last_sweep', None)
    now, owner = timezone.now(), uuid.uuid4()
    for minutes in (0, 1, 4, 5, 6):
        scheduler.dispatch_due(owner=owner, now=now + timedelta(minutes=minutes))
    assert runs == [now, now + timedelta(minutes=5)]
