"""Acquisition screens (FR-25) and side-by-side comparison (FR-27)."""
from datetime import timedelta
from django.db import transaction
from django.utils import timezone
from apps.locations.models import Location
from apps.locations.service import create_location, audit
from apps.operations.service import enqueue_job

SCREEN_TTL_DAYS = 30


def start_computations(location, actor=None):
    """Queue demographics and area data for a placed location (deduplicated per analysis version)."""
    jobs = []
    for kind, prefix in (('compute_ring_demographics', 'ring-demographics'), ('compute_area_profile', 'area-profile')):
        job, _ = enqueue_job(kind=kind, scope=f'location:{location.pk}',
            dedup_key=f'{prefix}:{location.pk}:{location.analysis_version}',
            parameters={'location_id': str(location.pk), 'analysis_version': location.analysis_version},
            requested_by=actor)
        jobs.append(str(job.pk))
    return jobs


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
    jobs = []
    if location.current_revision and location.current_revision.lat is not None:
        jobs = start_computations(location, actor)
    return location, lookup, status, jobs


def save_screen(location, actor):
    if not location.screening:
        return location
    location.screening = False
    location.version += 1
    location.save(update_fields=['screening', 'version', 'updated_at'])
    audit(location, actor, 'screen_saved', {'screening': True}, {'screening': False})
    return location


def expire_screens(now=None):
    """Archive unsaved screens older than 30 days (they were never monitored)."""
    cutoff = (now or timezone.now()) - timedelta(days=SCREEN_TTL_DAYS)
    stale = Location.objects.filter(screening=True, created_at__lt=cutoff).exclude(status='archived')
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
