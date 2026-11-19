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

# Only code-defined handlers are executable. No API accepts arbitrary Python paths.
REGISTRY={'sync_source_catalog':JobSpec(sync_source_catalog,'paragon-maintenance',1800),
    'compute_ring_demographics':JobSpec(compute_ring_demographics,'paragon-maintenance',900,
        frozenset({'location_id','analysis_version'}))}
