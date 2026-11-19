"""Compute and read ring demographics for a location (FR-09, MET-01..05)."""
import hashlib
from django.conf import settings
from django.db import IntegrityError, transaction
from apps.locations.models import Location
from apps.sources.health import record_check
from apps.sources.models import SourceSnapshot
from apps.sources.storage import LocalArtifactStore
from . import acs, cpi, geography
from .metrics import compute_rings
from .trends import ring_trends, unavailable
from .models import RingDemographics

DEFAULT_ACS_YEAR = 2024
BASELINE_ACS_YEAR = acs.LEGACY_YEAR
RADII = {'1/3/5': (1, 3, 5), '3/5/10': (3, 5, 10)}


class DemographicsUnavailable(Exception):
    """Raised with a reason code from docs/04 §7 and a plain-language message."""
    def __init__(self, code, message):
        self.code, self.message = code, message
        super().__init__(message)


def _store(store):
    return store or LocalArtifactStore(settings.SOURCE_ARTIFACT_ROOT)


def _latest(source_id, scope):
    return SourceSnapshot.objects.filter(source_id=source_id, scope=scope).order_by('-retrieved_at', '-published_at').first()


def ingest_acs(states, *, year=DEFAULT_ACS_YEAR, store=None, opener=None, line_source=None):
    store = _store(store)
    published = []
    for extract in acs.extract_states(year, states, opener=opener, line_source=line_source):
        snapshot, created = acs.publish_extract(extract, store)
        record_check(source_id='SRC-03', scope=snapshot.scope, run_key=f'ingest:{snapshot.sha256}',
            succeeded=True, completed_at=max(snapshot.retrieved_at, extract.retrieved_at), snapshot=snapshot,
            available_release=str(year))
        published.append((snapshot, created))
    return published


def _geography(lat, lon, radius, year, store, opener, decennial=2020):
    snapshot = _latest('SRC-04', geography.scope_for(lat, lon, radius, decennial))
    if snapshot and snapshot.context.get('acs_year') == year:
        return snapshot, geography.load_capture(snapshot, store)
    from apps.area.service import note_check
    scope = geography.scope_for(lat, lon, radius, decennial)
    try:
        capture = geography.fetch_geography(lat, lon, radius, acs_year=year, decennial=decennial, opener=opener)
    except geography.GeographyError as exc:
        note_check('SRC-04', scope, error='SOURCE_ERROR')
        raise DemographicsUnavailable('SOURCE_ERROR', f'Census {decennial} geography unavailable: {exc}') from None
    except OSError:
        note_check('SRC-04', scope, error='SOURCE_ERROR')
        raise DemographicsUnavailable('SOURCE_ERROR', f'Census {decennial} geography service unreachable') from None
    snapshot, _ = geography.publish_capture(capture, store)
    note_check('SRC-04', scope, snapshot=snapshot)
    return snapshot, capture


def _vintage_rings(lat, lon, radii, year, decennial, store, opener):
    geo_snapshot, capture = _geography(lat, lon, max(radii), year, store, opener, decennial)
    blocks, totals, mapping, unresolved = geography.parse_geography(capture)
    rows, acs_ids = {}, []
    for state in sorted({b.geoid[:2] for b in blocks}):
        snapshot = _latest('SRC-03', acs.scope_for(year, state))
        if snapshot is None:
            raise DemographicsUnavailable('NOT_COVERED',
                f'ACS {acs.vintage_period(year)} data for state {state} has not been ingested yet.')
        rows.update(acs.load_rows(snapshot, store))
        acs_ids.append(str(snapshot.pk))
    rings = compute_rings((lat, lon), radii, blocks, totals, mapping, unresolved, rows)
    return geo_snapshot, acs_ids, rings


def _cpi(years, store, opener):
    snapshot = _latest('SRC-08', cpi.SCOPE)
    if snapshot is None or not all(str(y) in snapshot.release.split('-') for y in years):
        try:
            values, retrieved = cpi.fetch(years, opener=opener)
        except (cpi.CpiError, OSError, ValueError, KeyError):
            from apps.area.service import note_check
            note_check('SRC-08', cpi.SCOPE, error='SOURCE_ERROR')
            raise DemographicsUnavailable('SOURCE_ERROR', 'BLS CPI unavailable for inflation adjustment.') from None
        snapshot, _ = cpi.publish(values, retrieved, store)
        from apps.area.service import note_check
        note_check('SRC-08', cpi.SCOPE, snapshot=snapshot)
    return snapshot, cpi.load(snapshot, store)


def compute_for_location(location_id, *, year=DEFAULT_ACS_YEAR, baseline_year=BASELINE_ACS_YEAR,
        store=None, opener=None):
    store = _store(store)
    location = Location.objects.select_related('current_revision').get(pk=location_id)
    revision = location.current_revision
    if revision is None or revision.lat is None:
        raise DemographicsUnavailable('NOT_PROVIDED', 'Place the pin before computing ring demographics.')
    radii = RADII[location.ring_preset]
    analysis_version = location.analysis_version
    lat, lon = revision.lat, revision.lon
    geo_snapshot, acs_ids, rings = _vintage_rings(lat, lon, radii, year, 2020, store, opener)
    baseline = {}
    try:
        base_geo, base_ids, base_rings = _vintage_rings(lat, lon, radii, baseline_year, 2010, store, opener)
        cpi_snapshot, cpi_values = _cpi((baseline_year, year), store, opener)
        cpi_ratio = cpi_values[str(year)] / cpi_values[str(baseline_year)]
        label = f'{cpi.LABEL}: {cpi_values[str(year)]} / {cpi_values[str(baseline_year)]} = {cpi_ratio:.4f}'
        for ring, base in zip(rings, base_rings):
            ring['baseline'] = {'acs_period': acs.vintage_period(baseline_year), 'metrics': base['metrics'],
                'method': {**base['method'], 'apportionment': 'decennial block-population weights (2010 Census blocks)'}}
            ring['trends'] = ring_trends(ring, base, cpi_ratio, label)
        baseline = {'acs_year': baseline_year, 'geography_snapshot_id': str(base_geo.pk),
            'acs_snapshot_ids': base_ids, 'cpi_snapshot_id': str(cpi_snapshot.pk), 'cpi_ratio': cpi_ratio}
    except DemographicsUnavailable as exc:
        for ring in rings:
            ring['trends'] = unavailable(exc.code, exc.message)
    inputs = [str(geo_snapshot.pk), *acs_ids, *(baseline and [baseline['geography_snapshot_id'],
        *baseline['acs_snapshot_ids'], baseline['cpi_snapshot_id']] or [])]
    inputs_sha = hashlib.sha256('|'.join(inputs).encode()).hexdigest()
    with transaction.atomic():
        current = Location.objects.select_for_update().get(pk=location.pk)
        if current.analysis_version != analysis_version:
            raise DemographicsUnavailable('STALE', 'The pin or ring preset changed during computation; retry.')
        try:
            with transaction.atomic():
                return RingDemographics.objects.create(location=location, revision=revision,
                    analysis_version=analysis_version, ring_preset=location.ring_preset, acs_year=year,
                    data_period=acs.vintage_period(year), geography_snapshot=geo_snapshot,
                    acs_snapshot_ids=acs_ids, baseline=baseline, inputs_sha256=inputs_sha, rings=rings)
        except IntegrityError:
            return RingDemographics.objects.get(location=location, analysis_version=analysis_version,
                acs_year=year, inputs_sha256=inputs_sha)


def current_result(location):
    """Latest result for the location's current pin and ring preset, or None."""
    return (RingDemographics.objects.filter(location=location, analysis_version=location.analysis_version)
        .select_related('geography_snapshot').order_by('-acs_year', '-computed_at').first())


def serialize(location, result):
    if result is None:
        latest_any = RingDemographics.objects.filter(location=location).order_by('-computed_at').first()
        placed = location.current_revision_id and location.current_revision.lat is not None
        return {'status': 'unavailable',
            'reason': 'NOT_PROVIDED' if not placed else ('STALE' if latest_any else 'NOT_COMPUTED'),
            'message': ('Place the pin to compute ring demographics.' if not placed else
                'The pin or ring preset changed; recompute ring demographics.' if latest_any else
                'Ring demographics have not been computed for this location yet.')}
    return {'status': 'available', 'ring_preset': result.ring_preset, 'acs_year': result.acs_year,
        'data_period': result.data_period, 'computed_at': result.computed_at,
        'pin': {'lat': result.revision.lat, 'lon': result.revision.lon, 'revision': str(result.revision_id)},
        'rings': result.rings,
        'sources': [
            {'id': 'SRC-03', 'name': 'U.S. Census Bureau, American Community Survey 5-year estimates',
             'tables': sorted(acs.TABLES), 'period': result.data_period,
             'url': 'https://www.census.gov/programs-surveys/acs/data/summary-file.html'},
            {'id': 'SRC-04', 'name': 'U.S. Census Bureau, 2020 Census blocks (TIGERweb)',
             'period': '2020 Census', 'retrieved_at': result.geography_snapshot.retrieved_at,
             'url': 'https://tigerweb.geo.census.gov/tigerwebmain/TIGERweb_restmapservice.html'},
            *([{'id': 'SRC-08', 'name': 'U.S. Bureau of Labor Statistics, CPI-U annual average (CUUR0000SA0)',
                'period': '2019 and 2024', 'url': 'https://www.bls.gov/cpi/'},
               {'id': 'SRC-03', 'name': 'U.S. Census Bureau, ACS 5-year sequence-based summary file (trend baseline)',
                'period': acs.vintage_period(result.baseline['acs_year']), 'url': acs.LEGACY_BASE}]
              if result.baseline else [])],
        'trend_baseline': result.baseline or None,
        'caveats': ['Survey estimates with 90% margins of error.',
            'Trends compare non-overlapping 5-year periods, each apportioned with its own census geography; '
            'only changes significant at 90% should be read as real.',
            'Describes the area around the pin, not this property.',
            'Median household income is interpolated from income brackets.']}
