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

# Only code-defined handlers are executable. No API accepts arbitrary Python paths.
REGISTRY={'sync_source_catalog':JobSpec(sync_source_catalog,'paragon-maintenance',1800)}
