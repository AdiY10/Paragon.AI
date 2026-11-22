"""Data-quality gate (redesign B6a): plausibility, consistency, freshness and golden values.

Every finding is {location, check, level, detail}; ``fail`` blocks `qa_report --strict`, ``warn`` does
not. Checks read only stored results, never fetch.
"""
from datetime import timedelta
from pathlib import Path
import re
from django.conf import settings
from django.utils import timezone
import yaml

# Days a section may go without recomputation, from its refresh schedule (config/schedules.yaml):
# economy and businesses weekly, traffic/jobs (annual sources check) and hazards monthly; plus slack.
SECTION_MAX_AGE_DAYS = {'economy': 21, 'businesses': 21, 'traffic': 45, 'hazards': 45, 'jobs': 45}
# Plausible annual average daily traffic by HPMS road class (vehicles/day).
AADT_RANGE = {'Interstate': (5_000, 400_000), 'Freeway/expressway': (3_000, 300_000),
    'Principal arterial': (1_500, 150_000), 'Minor arterial': (500, 80_000), 'Major collector': (100, 40_000),
    'Minor collector': (50, 25_000), 'Local': (10, 20_000)}
MAX_ROAD_DISTANCE_M = 250
# A leading token mixing letters and digits ("K120 Birch St", "EV2L Kindred St"), but not an ordinal ("16th St").
INVENTORY_CODE = re.compile(r'^(?!\d+(?:st|nd|rd|th)\b)(?=[A-Za-z]*\d)(?=\d*[A-Za-z])[A-Za-z0-9]{3,5}\s+[A-Za-z]', re.I)
MAX_BUSINESS_SWING = 0.20


def _finding(location, check, level, detail):
    return {'location': location.name, 'location_id': str(location.pk), 'check': check, 'level': level, 'detail': detail}


def _sections(location):
    from apps.area.models import AreaSection
    latest = {}
    for row in (AreaSection.objects.filter(location=location, analysis_version=location.analysis_version)
            .order_by('section', '-computed_at')):
        latest.setdefault(row.section, row)
    return latest


def _metric(ring, name):
    m = (ring.get('metrics') or {}).get(name) or {}
    return m.get('value'), m.get('reliability')


def check_location(location, now=None):
    from apps.area.analysis import missing_sections
    from apps.demographics.service import current_result
    from apps.demographics.vintage import current_acs_year
    now = now or timezone.now()
    out = []
    add = lambda check, level, detail: out.append(_finding(location, check, level, detail))  # noqa: E731
    missing = missing_sections(location)
    if missing:
        add('complete', 'fail', f'missing or outdated: {", ".join(missing)}')
    sections = _sections(location)

    demo = current_result(location)
    if demo is not None:
        rings = sorted(demo.rings, key=lambda r: r['radius_miles'])
        for name in ('population', 'households'):
            values = [_metric(r, name)[0] for r in rings]
            if None not in values and any(b < a for a, b in zip(values, values[1:])):
                add('rings_increase', 'fail', f'{name} shrinks with a larger ring: {[round(v) for v in values]}')
        for r in rings:
            pop, _ = _metric(r, 'population')
            hh, _ = _metric(r, 'households')
            if pop and hh and pop >= 1000 and not 0.2 <= hh / pop <= 0.7:
                add('households_per_person', 'fail', f'{r["radius_miles"]} mi: households/population = {hh / pop:.2f}')
            med, _ = _metric(r, 'median_household_income')
            mean, _ = _metric(r, 'mean_household_income')
            if med is not None and not 15_000 <= med <= 250_000:
                add('median_income_range', 'fail', f'{r["radius_miles"]} mi: median income ${med:,.0f}')
            if med is not None and mean and med > 1.3 * mean:
                add('median_vs_mean_income', 'fail', f'{r["radius_miles"]} mi: median ${med:,.0f} > 1.3 × mean ${mean:,.0f}')
        three = next((r for r in rings if r['radius_miles'] == 3), None)
        for name in ('population', 'households', 'median_household_income'):
            if three is not None and _metric(three, name)[1] == 'very_low':
                add('headline_reliability', 'fail', f'3 mi {name} has very low reliability')
        if demo.acs_year != current_acs_year():
            add('acs_vintage', 'fail', f'ACS {demo.acs_year}, current is {current_acs_year()}')

    jobs = sections.get('jobs')
    if jobs is not None and jobs.status == 'available':
        totals = [r['total'] for r in sorted(jobs.data.get('rings', []), key=lambda r: r['radius_miles'])]
        if any(b < a for a, b in zip(totals, totals[1:])):
            add('rings_increase', 'fail', f'jobs shrink with a larger ring: {totals}')

    traffic = sections.get('traffic')
    if traffic is not None and traffic.status == 'available' and traffic.data.get('roads'):
        road = traffic.data['roads'][0]
        low, high = AADT_RANGE.get(road.get('road_class'), (10, 400_000))
        if not low <= (road.get('aadt') or 0) <= high:
            add('aadt_plausible', 'fail', f'{road["label"]}: {road.get("aadt")} vehicles/day for a {road.get("road_class")}')
        if road.get('distance_m') is not None and road['distance_m'] > MAX_ROAD_DISTANCE_M:
            add('road_distance', 'fail', f'{road["label"]} is {road["distance_m"]} m from the pin')
        for r in traffic.data['roads']:
            if INVENTORY_CODE.match(r.get('label') or ''):
                add('road_label', 'fail', f'label looks like an inventory code: "{r["label"]}"')

    hazards = sections.get('hazards')
    if hazards is not None and hazards.status == 'available':
        at, near = hazards.data.get('flood_at_pin') or {}, hazards.data.get('flood_nearby') or {}
        if at.get('in_sfha', at.get('sfha')):
            zone = (near.get('zone') if near.get('inside') else at.get('zone')) or ''
            if not zone.upper().startswith(('A', 'V')):
                add('flood_zone_consistent', 'fail', f'inside a high-risk area but zone is "{zone}"')

    economy = sections.get('economy')
    tract = ((hazards.data.get('nri') or {}).get('tract') if hazards is not None else None)
    county = ((economy.data.get('county') or {}).get('fips') if economy is not None else None)
    if tract and county and tract[:5] != county:
        add('county_matches_tract', 'fail', f'county {county} but the pin\'s tract is {tract}')

    biz = sections.get('businesses')
    if biz is not None and biz.status == 'available':
        from apps.area.models import AreaSection
        previous = (AreaSection.objects.filter(location=location, section='businesses', status='available')
            .exclude(data__release=biz.data.get('release')).order_by('-computed_at').first())
        now_total = (biz.data.get('retail_and_services_total') or {}).get('3mi')
        before = (previous.data.get('retail_and_services_total') or {}).get('3mi') if previous else None
        if now_total and before and abs(now_total - before) / before > MAX_BUSINESS_SWING:
            add('business_count_swing', 'fail', f'3 mi count {before} → {now_total} between releases '
                f'{previous.data.get("release")} and {biz.data.get("release")}')

    for name, days in SECTION_MAX_AGE_DAYS.items():
        row = sections.get(name)
        if row is not None and row.computed_at < now - timedelta(days=days):
            add('fresh', 'fail', f'{name} last computed {row.computed_at:%Y-%m-%d} (refreshes every ≤{days} days)')
        if row is not None and any(s.get('stale') for s in row.sources or []):
            add('fresh', 'warn', f'{name} uses a cached copy after a source error')
    return out


def load_golden(path=None):
    doc = yaml.safe_load(Path(path or Path(settings.BASE_DIR) / 'config' / 'qa_golden.yaml').read_text())
    if doc.get('schema_version') != 1:
        raise ValueError('Unsupported golden file')
    return doc['golden']


def check_golden(entry):
    from apps.locations.models import Location
    from apps.demographics.service import current_result
    location = Location.objects.filter(status='owned', name__icontains=entry['location']).order_by('created_at').first()
    if location is None:
        return [{'location': entry['location'], 'location_id': None, 'check': 'golden', 'level': 'fail',
            'detail': 'property not found'}]
    sections = _sections(location)
    check, want, tol = entry['check'], entry['value'], entry.get('tolerance', 0)
    got = None
    if check == 'population':
        demo = current_result(location)
        ring = next((r for r in (demo.rings if demo else []) if r['radius_miles'] == entry['ring_miles']), None)
        got = _metric(ring, 'population')[0] if ring else None
    elif check == 'road_aadt':
        roads = (sections['traffic'].data.get('roads') or []) if 'traffic' in sections else []
        for r in roads:
            if entry['road'].lower() in (r.get('label') or '').lower():
                got = r['aadt'] if r.get('year') == entry['year'] else (
                    r.get('prior_aadt') if r.get('prior_year') == entry['year'] else None)
    elif check in ('flood_zone', 'base_flood_elevation_ft'):
        at = (sections['hazards'].data.get('flood_at_pin') or {}) if 'hazards' in sections else {}
        got = at.get('zone') if check == 'flood_zone' else at.get('bfe_ft')
    ok = (got == want) if isinstance(want, str) else (got is not None and abs(got - want) <= tol * abs(want) + 1e-9)
    if ok:
        return []
    label = f'{check}' + (f' {entry["ring_miles"]} mi' if 'ring_miles' in entry else '') + (f' {entry["road"]} {entry["year"]}' if 'road' in entry else '')
    return [_finding(location, 'golden', 'fail', f'{label}: expected {want}' + (f' ±{tol:.0%}' if tol else '') + f', got {got}')]


def report(locations=None, now=None):
    """All findings for owned, placed properties plus the golden values."""
    from apps.locations.models import Location
    if locations is None:
        locations = (Location.objects.filter(status='owned').exclude(current_revision__lat__isnull=True)
            .select_related('current_revision').order_by('name'))
    findings = []
    checked = 0
    for location in locations:
        checked += 1
        findings += check_location(location, now=now)
    for entry in load_golden():
        findings += check_golden(entry)
    return {'checked': checked, 'failures': sum(f['level'] == 'fail' for f in findings),
        'warnings': sum(f['level'] == 'warn' for f in findings), 'findings': findings}
