from dataclasses import dataclass
from collections.abc import Callable
from apps.sources.catalog import sync_catalog
from .contracts import JobResult

@dataclass(frozen=True)
class JobSpec:
    handler: Callable
    queue: str
    timeout_seconds: int
    parameter_keys: frozenset[str]=frozenset()
    # Seconds an attempt may go without a heartbeat before recovery may take it over.
    lease_seconds: int=600


def sync_source_catalog(context,parameters):
    context.heartbeat()
    return JobResult(records=sync_catalog())

def compute_ring_demographics(context,parameters):
    from apps.demographics.service import compute_for_location, DemographicsUnavailable
    from apps.locations.models import Location
    from .contracts import JobFailure
    context.heartbeat()
    location=Location.objects.get(pk=parameters['location_id'])
    if location.analysis_version!=parameters['analysis_version']:
        return JobResult(records=0)
    try:
        result=compute_for_location(location.pk)
    except DemographicsUnavailable as exc:
        raise JobFailure('SOURCE_ERROR' if exc.code=='SOURCE_ERROR' else 'NOT_CONFIGURED',
            retryable=exc.code=='SOURCE_ERROR') from None
    return JobResult(records=len(result.rings))

def compute_area_profile(context,parameters):
    from apps.area.service import compute_area
    from apps.area.http import SourceError
    from apps.locations.models import Location
    from .contracts import JobFailure
    context.heartbeat()
    location=Location.objects.get(pk=parameters['location_id'])
    if location.analysis_version!=parameters['analysis_version']:
        return JobResult(records=0)
    try:
        rows=compute_area(location.pk)
    except SourceError as exc:
        raise JobFailure('NOT_CONFIGURED' if exc.code=='NOT_PROVIDED' else 'SOURCE_ERROR',
            retryable=exc.code!='NOT_PROVIDED') from None
    unavailable={r.section:r.data.get('reason','UNAVAILABLE') for r in rows if r.status!='available'}
    return JobResult(records=len(rows)-len(unavailable),failed=len(unavailable),detail=unavailable)

def analyze_location(context,parameters):
    """Automatic analysis of one location (redesign B3a); same body on both queues."""
    from apps.area.analysis import Heartbeat,Stale,RETRYABLE,run_analysis
    context.heartbeat()
    try:
        with Heartbeat(context) as beat:
            outcome=run_analysis(parameters['location_id'],parameters['analysis_version'],parameters['sections'],check=beat.check)
    except Stale:
        return JobResult(records=0,detail={'stale':'STALE'})
    unavailable={k:v for k,v in outcome.items() if v!='available'}
    # Only transient source failures count as failed items; "not covered here" is a valid answer.
    return JobResult(records=len(outcome)-len(unavailable),
        failed=sum(1 for v in unavailable.values() if v in RETRYABLE),detail=unavailable)

def _refresh(fn):
    def handler(context,parameters):
        from .contracts import JobFailure
        out=fn(context)
        if out.done==0 and out.failed>0:
            raise JobFailure('SOURCE_ERROR')  # every location failed: a terminal failure, alerted on repeat
        return JobResult(records=out.done,failed=out.failed,detail=dict(list(out.failures.items())[:50]))
    return handler


def bls_bps_check(context,parameters):
    from apps.area.refresh import refresh_economy
    return _refresh(refresh_economy)(context,parameters)


def overture_check(context,parameters):
    from apps.area.refresh import refresh_businesses
    from apps.area.http import SourceError
    from .contracts import JobFailure
    try:
        return _refresh(refresh_businesses)(context,parameters)
    except SourceError as exc:
        raise JobFailure('SOURCE_ERROR' if exc.code not in JobFailure.CODES else exc.code) from None


def flood_recheck(context,parameters):
    from apps.area.refresh import refresh_hazards
    return _refresh(refresh_hazards)(context,parameters)


def annual_sources_check(context,parameters):
    from apps.area.refresh import refresh_annual
    return _refresh(refresh_annual)(context,parameters)

def brief_weekly(context,parameters):
    from apps.insights.brief import generate
    context.heartbeat()
    brief=generate(kind='weekly')
    return JobResult(records=len(brief.items)+len(brief.fyi))

def sec_daily(context,parameters):
    from apps.insights.sec import refresh_all
    from apps.area.http import SourceError
    from .contracts import JobFailure
    try:
        fetched,failed=refresh_all(context)
    except SourceError as exc:
        raise JobFailure(exc.code if exc.code in JobFailure.CODES else 'SOURCE_ERROR',retryable=exc.code!='NOT_CONFIGURED') from None
    if fetched==0 and failed>0:
        raise JobFailure('SOURCE_ERROR')
    return JobResult(records=fetched,failed=failed)

def maintenance_daily(context,parameters):
    """Housekeeping: expire unsaved screens, drop old finished job records and resolved alerts."""
    from datetime import timedelta
    from django.utils import timezone
    from apps.insights.screens import expire_screens
    from apps.accounts.models import LoginThrottle
    from .models import AlertEvent,JobRun
    context.heartbeat()
    now=timezone.now()
    done=expire_screens(now=now) or 0
    done+=JobRun.objects.filter(status__in=['succeeded','failed'],finished_at__lt=now-timedelta(days=180)).delete()[0]
    done+=AlertEvent.objects.filter(resolved_at__lt=now-timedelta(days=90)).delete()[0]
    done+=LoginThrottle.objects.filter(window_start__lt=now-timedelta(days=1)).delete()[0]
    # Raw Overture captures: keep the two newest releases; older ones live on in compact form.
    from django.conf import settings
    from apps.area import overture_store
    from apps.area.models import OvertureCapture
    from apps.sources.storage import LocalArtifactStore
    keep=sorted(set(OvertureCapture.objects.values_list('release',flat=True)))[-2:]
    done+=overture_store.prune_raw(LocalArtifactStore(settings.SOURCE_ARTIFACT_ROOT),keep)
    return JobResult(records=done)

FOREGROUND='paragon-foreground'
MAINTENANCE='paragon-maintenance'

# Only code-defined handlers are executable. No API accepts arbitrary Python paths.
REGISTRY={'sync_source_catalog':JobSpec(sync_source_catalog,MAINTENANCE,1800),
    # Foreground: user-triggered and short; never waits behind a multi-hour refresh.
    'compute_ring_demographics':JobSpec(compute_ring_demographics,FOREGROUND,1100,
        frozenset({'location_id','analysis_version'}),lease_seconds=1130),
    'compute_area_profile':JobSpec(compute_area_profile,FOREGROUND,900,
        frozenset({'location_id','analysis_version'})),
    'brief_weekly':JobSpec(brief_weekly,FOREGROUND,600),
    # Automatic analysis (B3a): user-facing on foreground; seeds, bulk and sweep work in the background.
    'analyze_location':JobSpec(analyze_location,FOREGROUND,900,
        frozenset({'location_id','analysis_version','sections'}),lease_seconds=300),
    'analyze_location_bg':JobSpec(analyze_location,MAINTENANCE,900,
        frozenset({'location_id','analysis_version','sections'}),lease_seconds=300),
    # Maintenance: scheduled refreshes (config/schedules.yaml), one location at a time.
    'bls_bps_check':JobSpec(bls_bps_check,MAINTENANCE,3600),
    'overture_check':JobSpec(overture_check,MAINTENANCE,7200),
    'flood_recheck':JobSpec(flood_recheck,MAINTENANCE,3600),
    'annual_sources_check':JobSpec(annual_sources_check,MAINTENANCE,7200),
    'sec_daily':JobSpec(sec_daily,MAINTENANCE,1800),
    'maintenance_daily':JobSpec(maintenance_daily,MAINTENANCE,600)}
