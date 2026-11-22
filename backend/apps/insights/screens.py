"""Acquisition screens (FR-25) and side-by-side comparison (FR-27)."""
from datetime import timedelta
from django.db import transaction
from django.utils import timezone
from apps.locations.models import Location
from apps.locations.service import create_location, audit

SCREEN_TTL_DAYS = 90  # unstarred new-place analyses (redesign B5); archived, never deleted
MAX_LIVE_ANALYSES = 6  # across all users: more queued analyses wait (429) rather than pile up
# Rough US boxes (lower 48, Alaska, Hawaii); the Census service then confirms a state.
US_BOUNDS = ((24.3, 49.6, -125.0, -66.8), (51.0, 71.6, -180.0, -129.9), (18.8, 22.4, -160.5, -154.6))


class OutsideUS(ValueError):
    pass


def in_us_bounds(lat, lon):
    return any(a <= lat <= b and c <= lon <= d for a, b, c, d in US_BOUNDS)


def too_busy():
    from apps.operations.models import JobRun
    return JobRun.objects.filter(kind='analyze_location', status__in=['queued', 'running', 'retrying']).count() >= MAX_LIVE_ANALYSES


def create_screen(*, address, name, actor, geocoder=None):
    """Create an unsaved candidate, geocode it, and start computations when the match is unambiguous."""
    from apps.locations.geocoding import request_lookup, accept_lookup
    from apps.locations.census import GeocoderError
    with transaction.atomic():
        location = create_location(name=name or address, address=address, actor=actor, status='candidate')
        location.screening = True
        location.save(update_fields=['screening', 'updated_at'])
    lookup, status = None, 'unplaced'
    try:
        lookup = request_lookup(location_id=location.pk, expected_version=location.version, actor=actor, fetcher=geocoder)
        status = lookup.status
        if lookup.status == 'matched' and len(lookup.candidates) == 1:
            location = accept_lookup(location_id=location.pk, lookup_id=lookup.pk, expected_version=location.version,
                candidate_index=0, actor=actor)
    except GeocoderError as exc:
        status = f'geocoder_{exc.code.lower()}'
    location.refresh_from_db()
    from apps.area.analysis import ensure_analysis
    job = ensure_analysis(location.pk, requested_by=actor)  # None while unplaced
    return location, lookup, status, [str(job.pk)] if job else []


def create_point_screen(*, lat, lon, label='', actor, fetcher=None):
    """A new-place analysis from a map click (redesign B5): pinned where clicked, named from the
    Census coordinates service ("Near Mount Kisco, NY"), analysis queued at once."""
    from apps.locations.census import fetch_point_geographies, GeocoderError
    from apps.area.analysis import ensure_analysis
    if not (isinstance(lat, (int, float)) and isinstance(lon, (int, float))) or not in_us_bounds(lat, lon):
        raise OutsideUS('Choose a point in the United States.')
    try:
        geo = (fetcher or fetch_point_geographies)(lat, lon)
    except GeocoderError:
        geo = {}  # the name can wait; the analysis does not need it
    if geo is None:
        raise OutsideUS('Choose a point in the United States.')
    where = ', '.join(p for p in (geo.get('place') or geo.get('county'), geo.get('state')) if p)
    name = (label or (f'Near {where}' if where else f'Map point {lat:.5f}, {lon:.5f}'))[:200]
    with transaction.atomic():
        location = create_location(name=name, address=f'Map point {lat:.5f}, {lon:.5f}', actor=actor,
            status='candidate', lat=float(lat), lon=float(lon), pin_method='manual', city=(geo.get('place') or '')[:120],
            state=(geo.get('state') or '')[:2], pin_context={'source': 'map point', 'county_fips': geo.get('county_fips'),
                'county': geo.get('county')})
        location.screening = True
        location.save(update_fields=['screening', 'updated_at'])
    return location, ensure_analysis(location.pk, requested_by=actor)


def keep_screen(location, kept):
    location.kept_at = timezone.now() if kept else None
    location.save(update_fields=['kept_at', 'updated_at'])
    return location


def expires_at(location):
    if not location.screening or location.kept_at:
        return None
    return location.created_at + timedelta(days=SCREEN_TTL_DAYS)


def save_screen(location, actor):
    if not location.screening:
        return location
    location.screening = False
    location.version += 1
    location.save(update_fields=['screening', 'version', 'updated_at'])
    audit(location, actor, 'screen_saved', {'screening': True}, {'screening': False})
    return location


def expire_screens(now=None):
    """Archive unstarred new-place analyses older than 90 days (never monitored; never deleted)."""
    cutoff = (now or timezone.now()) - timedelta(days=SCREEN_TTL_DAYS)
    stale = Location.objects.filter(screening=True, created_at__lt=cutoff, kept_at__isnull=True).exclude(status='archived')
    count = 0
    for location in stale:
        location.status = 'archived'
        location.version += 1
        location.save(update_fields=['status', 'version', 'updated_at'])
        audit(location, None, 'screen_expired', {'status': 'candidate'}, {'status': 'archived'})
        count += 1
    return count


def compare(ids):
    """Rows of comparable measures for 2-4 locations plus portfolio median and range."""
    from .metrics import METRICS, extract, benchmarks
    from .signals import cached_attention, active_for
    locations = list(Location.objects.filter(pk__in=ids).select_related('current_revision', 'metrics_snapshot'))
    order = {str(i): n for n, i in enumerate(ids)}
    locations.sort(key=lambda l: order.get(str(l.pk), 99))
    values = {str(l.pk): extract(l) for l in locations}
    bench = benchmarks()
    rows = []
    for key, (label, unit, direction, group) in METRICS.items():
        cells = {lid: (v.get(key) or {}) for lid, v in values.items()}
        nums = [c['value'] for c in cells.values() if c.get('value') is not None]
        best = worst = None
        if len(nums) >= 2 and len(set(nums)) > 1:
            best = max(nums) if direction == 'up' else min(nums)
            worst = min(nums) if direction == 'up' else max(nums)
        rows.append({'key': key, 'label': label, 'unit': unit, 'direction': direction, 'group': group,
            'cells': {lid: {'value': c.get('value'), 'period': c.get('period'), 'source': c.get('source'),
                'detail': c.get('detail'), 'best': c.get('value') is not None and c.get('value') == best,
                'worst': c.get('value') is not None and c.get('value') == worst} for lid, c in cells.items()},
            'portfolio': bench.get(key)})
    cols = []
    for l in locations:
        hz = values[str(l.pk)].get('_hazards') or {}
        at = hz.get('flood_at_pin') or {}
        cols.append({'id': str(l.pk), 'name': l.name, 'city': l.city, 'state': l.state, 'status': l.status,
            'screening': l.screening, 'ring_preset': l.ring_preset, 'attention': cached_attention(l),
            'flood_zone': at.get('zone'), 'sfha': bool(at.get('in_sfha', at.get('sfha'))),
            'nri_rating': (hz.get('nri') or {}).get('rating'),
            'signals': [{'title': s['title'], 'severity': s['severity']} for s in active_for(l)][:5]})
    return {'locations': cols, 'rows': rows,
        'note': 'Area indicators on the 3-mile ring (county or road level where noted); not property results. '
            'Best and weakest are highlighted only for measures where higher or lower is clearly better.'}
