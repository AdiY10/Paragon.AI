"""Automatic analysis (redesign B3a): every placed location gets its full analysis without a button.

One analysis = ring demographics + the five area sections, computed for the location's current
``analysis_version`` (a pin move or ring change starts a new version). Entry points:

- ``ensure_analysis``: called after a location is created, re-pinned or re-ringed (on commit), when a
  new place is analyzed, and by the sweep. Idempotent: returns the live job when there is one.
- ``run_analysis``: the job body; computes sections one by one, checks for a newer pin between
  sections, and evaluates alerts once at the end.
- ``sweep``: run by the scheduler at most every 5 minutes; fills missing sections, retries
  transient source failures with backoff, recomputes outdated logic versions, and raises an admin
  alert for an owned property that has no pin.

Job keys are ``analyze:{location}:{analysis_version}:{attempt}``: a new attempt after a failure gets
a new key, so ``enqueue_job``'s one-job-per-key rule (which scheduled jobs rely on) is unchanged.
"""
from datetime import timedelta
import logging
import threading
from django.db import connection, transaction
from django.utils import timezone
from apps.locations.models import Location
from apps.operations.models import JobRun
from .models import AreaSection
from .service import SECTIONS as AREA_SECTIONS, SECTION_LOGIC

log = logging.getLogger(__name__)

# Fast sections first so the page fills in progressively; demographics can take minutes the first
# time a state is seen (ACS ingest).
ORDER = ('hazards', 'traffic', 'economy', 'businesses', 'jobs', 'demographics')
ALL_SECTIONS = frozenset(ORDER)
assert ALL_SECTIONS == {'demographics', *AREA_SECTIONS}
FOREGROUND_KIND, BACKGROUND_KIND = 'analyze_location', 'analyze_location_bg'
KINDS = (FOREGROUND_KIND, BACKGROUND_KIND)
LIVE = (JobRun.Status.QUEUED, JobRun.Status.RUNNING, JobRun.Status.RETRYING)
FINISHED = (JobRun.Status.SUCCEEDED, JobRun.Status.FAILED)
# Source failures worth another try later; anything else (not covered, no station nearby) is an answer.
RETRYABLE = frozenset({'TIMEOUT', 'HTTP_ERROR', 'SOURCE_ERROR'})
# Wait after the Nth finished attempt at the same analysis version before the sweep tries again.
BACKOFF = (timedelta(0), timedelta(minutes=10), timedelta(hours=2), timedelta(hours=24))
MAX_FAILED_PER_DAY = 3
SWEEP_EVERY = timedelta(minutes=5)


class Stale(Exception):
    """The pin or ring preset changed while the analysis ran; the newer version has its own job."""


def _placed(location):
    revision = location.current_revision
    return revision is not None and revision.lat is not None


def _attempts(location):
    return JobRun.objects.filter(kind__in=KINDS, scope=f'location:{location.pk}',
        dedup_key__startswith=f'analyze:{location.pk}:{location.analysis_version}:')


def missing_sections(location):
    """Sections without a usable result for the current analysis version, in run order."""
    from apps.demographics.models import RingDemographics
    from apps.demographics.service import LOGIC_VERSION
    av = location.analysis_version
    missing = []
    demo = (RingDemographics.objects.filter(location=location, analysis_version=av)
        .order_by('-computed_at').only('logic_version').first())
    if demo is None or demo.logic_version < LOGIC_VERSION:
        missing.append('demographics')
    latest = {}
    for row in (AreaSection.objects.filter(location=location, analysis_version=av)
            .order_by('section', '-computed_at').only('section', 'status', 'data', 'logic_version')):
        latest.setdefault(row.section, row)
    for name in AREA_SECTIONS:
        row = latest.get(name)
        if (row is None or row.logic_version < SECTION_LOGIC[name]
                or (row.status == 'unavailable' and (row.data or {}).get('reason') in RETRYABLE)):
            missing.append(name)
    return [s for s in ORDER if s in missing]


def ensure_analysis(location_id, sections=None, *, interactive=True, requested_by=None, now=None):
    """Queue an analysis unless one is live; returns the live or new job, or None.

    ``sections=None`` queues only what is missing (nothing missing → None). Explicit sections are
    recomputed. Archived and unplaced locations are skipped; after ``MAX_FAILED_PER_DAY`` failed
    attempts in 24 hours the sweep stops retrying until the window passes.
    """
    from apps.operations.service import enqueue_job
    if sections is not None and (not sections or not set(sections) <= ALL_SECTIONS):
        raise ValueError('Unknown analysis section')
    now = now or timezone.now()
    with transaction.atomic():
        # Lock only the location row (current_revision is a nullable join; Postgres refuses to lock it).
        location = Location.objects.select_for_update().get(pk=location_id)
        if location.status == Location.Status.ARCHIVED or not _placed(location):
            return None
        attempts = _attempts(location)
        live = attempts.filter(status__in=LIVE).order_by('-created_at').first()
        if live is not None:
            return live
        if attempts.filter(status=JobRun.Status.FAILED, finished_at__gte=now - timedelta(hours=24)).count() >= MAX_FAILED_PER_DAY:
            return None
        if sections is None:
            sections = missing_sections(location)
            if not sections:
                return None
        sections = [s for s in ORDER if s in set(sections)]
        number = attempts.count() + 1
        job, _ = enqueue_job(kind=FOREGROUND_KIND if interactive else BACKGROUND_KIND,
            scope=f'location:{location.pk}',
            dedup_key=f'analyze:{location.pk}:{location.analysis_version}:{number}',
            parameters={'location_id': str(location.pk), 'analysis_version': location.analysis_version,
                'sections': sections},
            requested_by=requested_by)
        return job


def run_analysis(location_id, analysis_version, sections, *, check=None, store=None, opener=None, capturer=None):
    """Compute the requested sections; returns {section: 'available' | reason code}.

    ``check`` is called between sections (heartbeat / cancellation); it raises to stop the run.
    Raises ``Stale`` when the location moved on to a newer analysis version.
    """
    from apps.demographics.service import compute_for_location, DemographicsUnavailable
    from .http import SourceError
    from .service import compute_section, _store
    store = _store(store)
    outcome = {}
    for name in [s for s in ORDER if s in set(sections)]:
        if check is not None:
            check()
        location = Location.objects.select_related('current_revision').get(pk=location_id)
        if location.analysis_version != analysis_version or not _placed(location):
            raise Stale()
        try:
            if name == 'demographics':
                compute_for_location(location.pk, store=store, opener=opener, evaluate=False)
                outcome[name] = 'available'
            else:
                row = compute_section(location, location.current_revision, analysis_version, name,
                    store=store, opener=opener, capturer=capturer)
                outcome[name] = 'available' if row.status == 'available' else (row.data or {}).get('reason', 'UNAVAILABLE')
        except (DemographicsUnavailable, SourceError) as exc:
            if exc.code == 'STALE':
                raise Stale() from None
            outcome[name] = exc.code
    if any(v == 'available' for v in outcome.values()):
        from apps.insights.signals import safe_evaluate
        safe_evaluate(location_id)
    return outcome


class Heartbeat:
    """Renews the job lease from a side thread during long sections; ``check`` stops a fenced run.

    The main thread also heartbeats between sections (``check``), so a recovered attempt stops at
    the next section boundary instead of writing results twice.
    """
    def __init__(self, context, every=60):
        self.context, self.every = context, every
        self.fenced = False
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, name='analysis-heartbeat', daemon=True)

    def _loop(self):
        try:
            while not self._stop.wait(self.every):
                try:
                    self.context.heartbeat()
                except Exception:
                    self.fenced = True
                    return
        finally:
            connection.close()  # this thread's own DB connection

    def check(self):
        from apps.operations.contracts import JobFailure
        if self.fenced:
            raise JobFailure('SOURCE_ERROR', retryable=False)
        self.context.heartbeat()

    def __enter__(self):
        self._thread.start()
        return self

    def __exit__(self, *exc):
        self._stop.set()
        self._thread.join(timeout=5)
        return False


def _backoff_ok(location, now):
    finished = _attempts(location).filter(status__in=FINISHED, finished_at__isnull=False)
    n = finished.count()
    if n == 0:
        return True
    last = finished.order_by('-finished_at').values_list('finished_at', flat=True).first()
    return last + BACKOFF[min(n, len(BACKOFF) - 1)] <= now


def _unplaced_alerts(now):
    from apps.operations.alerts import raise_alert, resolve_alert
    from apps.operations.models import AlertEvent
    owned = Location.objects.filter(status=Location.Status.OWNED).select_related('current_revision')
    for location in owned:
        key = f'location:{location.pk}:unplaced'
        if _placed(location):
            resolve_alert(key)
        elif not AlertEvent.objects.filter(key=key, resolved_at__isnull=True).exists():
            # Owned property names are not confidential; never put addresses or coordinates here.
            raise_alert(key, f'Owned property "{location.name}" has no map pin, so its analysis cannot run')


def sweep(now=None, limit=2):
    """Queue background analyses for locations with missing or outdated sections.

    Keeps at most ``limit`` background analyses live, so bulk work never floods the queue.
    """
    now = now or timezone.now()
    try:
        _unplaced_alerts(now)
    except Exception:
        log.exception('unplaced-property alert bookkeeping failed')
    room = limit - JobRun.objects.filter(kind=BACKGROUND_KIND, status__in=LIVE).count()
    queued = 0
    if room <= 0:
        return {'queued': 0}
    candidates = (Location.objects.exclude(status=Location.Status.ARCHIVED)
        .exclude(current_revision__isnull=True).exclude(current_revision__lat__isnull=True)
        .select_related('current_revision').order_by('created_at'))
    for location in sorted(candidates, key=lambda l: l.status != Location.Status.OWNED):  # owned first
        if queued >= room:
            break
        if _attempts(location).filter(status__in=LIVE).exists() or not missing_sections(location):
            continue
        if not _backoff_ok(location, now):
            continue
        try:
            job = ensure_analysis(location.pk, interactive=False, now=now)
        except Exception:
            log.exception('could not queue analysis for location %s', location.pk)
            continue
        if job is not None:
            queued += 1
    return {'queued': queued}


def wake_demographics(limit=50):
    """After an ACS ingest: queue demographics for placed locations still waiting for them."""
    woken = 0
    for location in (Location.objects.exclude(status=Location.Status.ARCHIVED)
            .exclude(current_revision__isnull=True).exclude(current_revision__lat__isnull=True)
            .select_related('current_revision').order_by('-created_at')):
        if woken >= limit:
            break
        if 'demographics' not in missing_sections(location) or _attempts(location).filter(status__in=LIVE).exists():
            continue
        if ensure_analysis(location.pk, ['demographics'], interactive=location.screening) is not None:
            woken += 1
    return woken


def analyze_after_commit(location_id, actor=None):
    """Hook for location changes: queue the analysis once the change is committed (``AUTO_ANALYZE``)."""
    from django.conf import settings
    if not getattr(settings, 'AUTO_ANALYZE', False):
        return
    interactive = actor is not None  # seed imports and other bulk work use the background queue

    def go():
        try:
            ensure_analysis(location_id, interactive=interactive, requested_by=actor)
        except Exception:
            log.exception('could not queue analysis for location %s', location_id)
    transaction.on_commit(go)
