"""Which ACS 5-year vintage the product uses (R2 item 9).

The current vintage is the newest one ingested for every state the monitored portfolio
needs; until a new vintage covers all of them, everything stays on the previous one, so
properties are never compared across vintages. Labels come from the year, never from code.
"""
from apps.sources.models import SourceSnapshot

FALLBACK_YEAR = 2024
FIRST_TABLE_BASED_YEAR = 2021


def required_states():
    """Two-digit FIPS codes for monitored properties' states and their neighbours."""
    from apps.area.refresh import monitored
    from apps.demographics.management.commands.ingest_acs import FIPS, NEIGHBOURS
    states = set()
    for location in monitored():
        if location.state in FIPS:
            states |= {FIPS[s] for s in [location.state, *NEIGHBOURS.get(location.state, [])] if s in FIPS}
    return states


def ingested_years():
    """{year: set(states)} for table-based vintages."""
    out = {}
    for release, scope in SourceSnapshot.objects.filter(source_id='SRC-03', scope__contains=':bg:').values_list('release', 'scope'):
        if release.isdigit() and int(release) >= FIRST_TABLE_BASED_YEAR:
            out.setdefault(int(release), set()).add(scope.rsplit(':', 1)[1])
    return out


def current_acs_year(states=None):
    states = required_states() if states is None else set(states)
    complete = [y for y, have in ingested_years().items() if states <= have]
    return max(complete) if complete else FALLBACK_YEAR


def geography_year(year):
    """TIGERweb ACS service used for block-group GEOIDs. 2022+ vintages share the same codes
    (Connecticut planning regions), so one mapping serves them all and a new vintage does not
    depend on its TIGERweb service being published."""
    return year if year < 2022 else 2024


def period_label(year):
    return f'{year - 4}–{year}'


def trend_period(baseline_year, year):
    return f'{period_label(baseline_year)} → {period_label(year)}'
