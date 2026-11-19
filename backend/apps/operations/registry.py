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
    return JobResult(records=len(rows))

def _refresh(fn):
    def handler(context,parameters):
        result=fn(context)
        return JobResult(records=result[0])
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

# Only code-defined handlers are executable. No API accepts arbitrary Python paths.
REGISTRY={'sync_source_catalog':JobSpec(sync_source_catalog,'paragon-maintenance',1800),
    'compute_ring_demographics':JobSpec(compute_ring_demographics,'paragon-maintenance',900,
        frozenset({'location_id','analysis_version'})),
    'compute_area_profile':JobSpec(compute_area_profile,'paragon-maintenance',900,
        frozenset({'location_id','analysis_version'})),
    # Scheduled refreshes (config/schedules.yaml); long-running, one location at a time.
    'bls_bps_check':JobSpec(bls_bps_check,'paragon-maintenance',3600),
    'overture_check':JobSpec(overture_check,'paragon-maintenance',7200),
    'flood_recheck':JobSpec(flood_recheck,'paragon-maintenance',3600),
    'annual_sources_check':JobSpec(annual_sources_check,'paragon-maintenance',7200),
    'brief_weekly':JobSpec(brief_weekly,'paragon-maintenance',600)}
