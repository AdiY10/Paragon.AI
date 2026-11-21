"""Scheduled refreshes (docs/06 §4.1): keep monitored locations current without manual runs.

Each handler is idempotent: section rows are keyed by their input snapshots, so a
run that finds no newer source period stores nothing new. Per-location failures are
counted and skipped; one bad location never stops the batch.
"""
from dataclasses import dataclass, field
import logging
from django.conf import settings
from apps.locations.models import Location
from apps.sources.models import SourceSnapshot
from .http import SourceError, fetch
from . import overture

MONITORED_STATUSES = ('owned', 'candidate')
log = logging.getLogger(__name__)


@dataclass
class Outcome:
    """What a refresh did: done/failed location counts, failure codes by location id, extra info."""
    done: int = 0
    failed: int = 0
    failures: dict = field(default_factory=dict)
    info: dict = field(default_factory=dict)

    def add(self, other):
        self.done += other.done
        self.failed += other.failed
        self.failures.update(other.failures)
        return self


def _code(exc):
    return getattr(exc, 'code', None) or type(exc).__name__


def monitored():
    """Owned and candidate locations with a pin. Archived and unsaved screens are excluded."""
    qs = (Location.objects.filter(status__in=MONITORED_STATUSES)
        .exclude(current_revision__lat__isnull=True).select_related('current_revision'))
    if hasattr(Location, 'screening'):
        qs = qs.filter(screening=False)
    return qs.order_by('name')


def _each(context, sections, **kwargs):
    from .service import compute_area
    out = Outcome()
    for location in monitored():
        context.heartbeat()
        try:
            compute_area(location.pk, sections=sections, **kwargs)
            out.done += 1
        except Exception as exc:
            out.failed += 1
            out.failures[str(location.pk)] = _code(exc)
            log.warning('refresh %s failed for location %s: %s', '+'.join(sections), location.pk, _code(exc))
    return out


def refresh_economy(context, **kwargs):
    """Weekly: QCEW quarter, LAUS month and BPS month (cached 7 days, so a weekly run re-checks)."""
    return _each(context, ('economy',), **kwargs)


def refresh_businesses(context, *, opener=None, **kwargs):
    """Weekly: capture the newest Overture release for every monitored pin before older releases expire."""
    from apps.area.service import note_check
    try:
        releases = overture.available_releases(opener=opener)
        note_check('SRC-13', 'releases', snapshot=None)
    except SourceError as exc:
        note_check('SRC-13', 'releases', error=exc.code)
        raise
    out = _each(context, ('businesses',), opener=opener, **kwargs)
    out.info['release'] = releases[-1]
    return out


def refresh_hazards(context, **kwargs):
    """Monthly: FEMA flood maps change as revisions take effect; NRI is cached 90 days."""
    return _each(context, ('hazards',), **kwargs)


ACS_PROBE = 'https://www2.census.gov/programs-surveys/acs/summary_file/{year}/table-based-SF/data/5YRData/acsdt5y{year}-b01003.dat'


def newest_acs_year(*, opener=None, today=None):
    """Newest 5-year vintage whose bulk files are published (probe a small byte range)."""
    from datetime import date
    year = (today or date.today()).year
    for candidate in range(year - 1, year - 4, -1):
        try:
            fetch(ACS_PROBE.format(year=candidate), opener=opener, retries=0, max_bytes=64 * 1024 * 1024,
                headers={'Range': 'bytes=0-63'})
            return candidate
        except SourceError as exc:
            # Census answers 401/403 for staged, not-yet-public vintages and 404 for absent ones.
            if exc.code != 'NOT_COVERED' and not (exc.code == 'HTTP_ERROR' and exc.detail in ('401', '403')):
                raise
    return None


def ingested_acs_states(year):
    return {scope.rsplit(':', 1)[1] for scope in SourceSnapshot.objects.filter(
        source_id='SRC-03', release=str(year)).values_list('scope', flat=True)}


def refresh_annual(context, *, opener=None, acs_opener=None, **kwargs):
    """Monthly: new ACS vintage -> ingest and recompute demographics; then traffic and jobs (new HPMS/LODES years)."""
    from apps.demographics.service import ingest_acs, compute_for_location
    from apps.demographics.acs import LEGACY_YEAR
    from apps.demographics.vintage import required_states, current_acs_year
    from apps.demographics.service import current_result
    states = required_states()
    out = Outcome()
    year = newest_acs_year(opener=acs_opener)
    # Ingest every required state for the newest vintage once; the portfolio switches only
    # when all of them are in (current_acs_year), never per screen.
    if year and states - ingested_acs_states(year):
        context.heartbeat()
        ingest_acs(sorted(states - ingested_acs_states(year)), year=year, opener=acs_opener)
    if states - ingested_acs_states(LEGACY_YEAR):
        ingest_acs(sorted(states - ingested_acs_states(LEGACY_YEAR)), year=LEGACY_YEAR, opener=acs_opener)
    current = current_acs_year(states)
    for location in monitored():
        result = current_result(location)
        if result is not None and result.acs_year == current:
            continue
        context.heartbeat()
        try:
            compute_for_location(location.pk, year=current)
            out.done += 1
        except Exception as exc:
            out.failed += 1
            out.failures[str(location.pk)] = _code(exc)
            log.warning('demographics refresh failed for location %s: %s', location.pk, _code(exc))
    year = current
    out.add(_each(context, ('traffic', 'jobs'), opener=opener, **kwargs))
    out.info['acs_year'] = year
    return out
