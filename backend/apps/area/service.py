"""Compute economy, traffic and hazard sections for a location (FR-11, FR-12, FR-13, FR-15).

Each section is computed independently: one failing source never blanks the
others, and a failure is stored with its reason rather than a guessed value.
Raw source responses are published as immutable snapshots for provenance and
reused while fresh, so repeated page views do not re-query public services.
"""
from datetime import timedelta
import hashlib
import io
import json
import logging
from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone
from apps.demographics.rings import haversine_miles
from apps.locations.models import Location
from apps.sources.models import SourceHealth, SourceSnapshot
from apps.sources.snapshots import publish_snapshot, ValidationReport
from apps.sources.storage import LocalArtifactStore
from . import economy as econ
from . import traffic_hazards as th
from . import businesses as biz
from . import overture
from . import jobs as lodes
from .http import SourceError
from .models import AreaSection

ADAPTER = 'area-v1'
# Bump a section's logic version when its computation changes, so cached results are recomputed.
SECTION_LOGIC = {'businesses': 5, 'hazards': 3}
log = logging.getLogger(__name__)
SECTIONS = ('economy', 'traffic', 'hazards', 'businesses', 'jobs')
SOURCE_META = {
    'SRC-04': ('U.S. Census Bureau, TIGERweb counties', 'https://tigerweb.geo.census.gov/tigerwebmain/TIGERweb_restmapservice.html'),
    'SRC-06': ('U.S. Bureau of Labor Statistics, Quarterly Census of Employment and Wages', 'https://www.bls.gov/cew/'),
    'SRC-07': ('U.S. Bureau of Labor Statistics, Local Area Unemployment Statistics', 'https://www.bls.gov/lau/'),
    'SRC-09': ('U.S. Census Bureau, Building Permits Survey', 'https://www.census.gov/construction/bps/'),
    'SRC-10': ('FHWA Highway Performance Monitoring System (USDOT)', 'https://www.fhwa.dot.gov/policyinformation/hpms.cfm'),
    'SRC-11': ('FEMA National Flood Hazard Layer', 'https://www.fema.gov/flood-maps/national-flood-hazard-layer'),
    'SRC-12': ('FEMA National Risk Index', 'https://hazards.fema.gov/nri/'),
    'SRC-05': ('U.S. Census Bureau, LEHD Origin-Destination Employment Statistics (LODES 8)',
        'https://lehd.ces.census.gov/data/#lodes'),
    'SRC-13': ('Overture Maps Places (© Overture Maps Foundation; CDLA-Permissive-2.0, Apache-2.0, CC0)',
        'https://docs.overturemaps.org/attribution/'),
}


def _store(store):
    return store or LocalArtifactStore(settings.SOURCE_ARTIFACT_ROOT)


HEALTH_CODES = {'TIMEOUT', 'HTTP_ERROR', 'SCHEMA_ERROR', 'NOT_CONFIGURED', 'STORAGE_ERROR', 'SOURCE_ERROR'}


def note_check(source_id, scope, *, snapshot=None, error=None):
    """Record a scoped source check for the Data Sources page (FR-30/31). Never raises."""
    from apps.sources.health import record_check
    import uuid
    try:
        if error is None:
            record_check(source_id=source_id, scope=scope[:160], run_key=f'area:{uuid.uuid4()}', succeeded=True,
                completed_at=timezone.now(), snapshot=snapshot if snapshot and snapshot.scope == scope[:160] else None)
        elif error in HEALTH_CODES:
            record_check(source_id=source_id, scope=scope[:160], run_key=f'area:{uuid.uuid4()}', succeeded=False,
                completed_at=timezone.now(), error_code=error)
    except Exception:  # health bookkeeping must never break a computation
        log.exception('source health bookkeeping failed for %s', source_id)


class Run:
    """Collects snapshots and source citations for one section computation."""
    def __init__(self, store, opener):
        self.store, self.opener, self.snapshots, self.sources = store, opener, [], {}

    def cached(self, source_id, scope, max_age_days, fetcher, *, release_match=None):
        """Reuse a fresh snapshot, else fetch, validate and publish. Returns (raw, snapshot).

        If a refresh fails but an older snapshot exists, the older one is used and the
        citation is marked stale with its date (docs/04 §7 CACHED_AFTER_ERROR).
        """
        # Freshness comes from the last successful check, not the snapshot: snapshots are
        # content-addressed, so an unchanged re-fetch keeps its original retrieved_at.
        health = (SourceHealth.objects.filter(source_id=source_id, scope=scope[:160])
            .select_related('latest_snapshot').first())
        snap = health.latest_snapshot if health and health.latest_snapshot_id else (
            SourceSnapshot.objects.filter(source_id=source_id, scope=scope[:160])
            .order_by('-retrieved_at', '-published_at').first())
        checked = max(filter(None, [snap and snap.retrieved_at, health and health.last_success_at]), default=None)
        fresh = snap and (max_age_days is None or checked >= timezone.now() - timedelta(days=max_age_days))
        stale_error = None
        if fresh and (release_match is None or snap.release == release_match):
            with self.store.open_verified(snap.artifact_key) as handle:
                raw = handle.read()
        else:
            try:
                raw, url, release, period = fetcher()
                snap, _ = publish_snapshot(source_id=source_id, scope=scope[:160], release=str(release)[:96],
                    data_period=period[:160], source_url=url, adapter_version=ADAPTER, stream=io.BytesIO(raw),
                    store=self.store, validation=ValidationReport(True, True, {'format': 'raw response'}, 1))
                note_check(source_id, scope, snapshot=snap)
                checked = timezone.now()
            except SourceError as exc:
                note_check(source_id, scope, error=exc.code)
                if snap is None or exc.code == 'NOT_COVERED':
                    raise
                stale_error = exc.code
                with self.store.open_verified(snap.artifact_key) as handle:
                    raw = handle.read()
        self.snapshots.append(str(snap.pk))
        name, link = SOURCE_META[source_id]
        entry = self.sources.setdefault(source_id + snap.data_period, {'id': source_id, 'name': name, 'url': link,
            'period': snap.data_period, 'retrieved_at': snap.retrieved_at.isoformat(),
            'checked_at': (checked or snap.retrieved_at).isoformat(), 'stale': False})
        if stale_error:
            entry.update(stale=True, stale_reason=stale_error)
        return raw, snap


def _pin_key(lat, lon):
    return f'{lat:.6f},{lon:.6f}'


def county_for(run, lat, lon):
    raw, _ = run.cached('SRC-04', f'county:{_pin_key(lat, lon)}', None,
        lambda: (econ.fetch_county(lat, lon, opener=run.opener), econ.COUNTY_URL, 'ACS2024', 'Counties (ACS 2024 vintage)'))
    return econ.parse_county(raw)


def _part(fn):
    try:
        return fn()
    except SourceError as exc:
        return {'value': None, 'reason': exc.code}


def economy_section(run, lat, lon):
    county = county_for(run, lat, lon)
    fips = county['fips']

    def employment():
        def fetch():
            raw, y, q, url = econ.fetch_qcew_latest(fips, opener=run.opener)
            return raw, url, f'{y}Q{q}', f'{y} Q{q}'
        raw, snap = run.cached('SRC-06', f'qcew:{fips}', 7, fetch)
        return {'period': snap.data_period, **{('private' if k == '10' else 'retail'): v
            for k, v in econ.parse_qcew(raw, fips).items()}}

    def unemployment():
        def fetch():
            raw, url = econ.fetch_laus(fips, opener=run.opener)
            parsed = econ.parse_laus(raw, fips)
            return raw, url, parsed['period'], parsed['period'] + (' (preliminary)' if parsed['preliminary'] else '')
        raw, _ = run.cached('SRC-07', f'laus:{fips}', 7, fetch)
        return econ.parse_laus(raw, fips)

    def permits():
        def latest():
            yyyymm, raw, url = econ.latest_bps_month(opener=run.opener)
            return raw, url, str(yyyymm), f'Year to date, {yyyymm // 100}-{yyyymm % 100:02d}'
        _, latest_snap = run.cached('SRC-09', 'bps:county:latest', 7, latest)
        yyyymm = int(latest_snap.release)
        files = {}
        for key, (y, m) in econ.bps_months(yyyymm).items():
            def fetch(y=y, m=m):
                raw, url = econ.fetch_bps_file(y, m, opener=run.opener)
                return raw, url, f'{y}{m:02d}', f'Year to date, {y}-{m:02d}'
            files[key], _ = run.cached('SRC-09', f'bps:county:{y}{m:02d}y', None, fetch)
        result = econ.bps_trailing(files, fips)
        y, m = divmod(yyyymm, 100)
        result['period'] = f'12 months to {y}-{m:02d}'
        result['prior_period'] = f'12 months to {y - 1}-{m:02d}'
        return result

    data = {'county': county, 'employment': _part(employment), 'unemployment': _part(unemployment),
        'permits': _part(permits)}
    return data, any(v.get('reason') is None for k, v in data.items() if k != 'county')


def traffic_section(run, lat, lon):
    county = county_for(run, lat, lon)
    state = county['fips'][:2]

    def latest():
        raw, url, year = th.fetch_hpms_latest(state, lat, lon, opener=run.opener)
        return raw, url, str(year), f'HPMS {year}'
    # 'hpms2' scopes carry road geometry (distance to the pin); older captures did not.
    raw, snap = run.cached('SRC-10', f'hpms2:{_pin_key(lat, lon)}', 30, latest)
    year = int(snap.release)
    roads = th.primary_roads(th.parse_hpms(raw, lat, lon))
    prior = []
    try:
        def fetch_prior():
            raw, url = th.fetch_hpms(state, year - 1, lat, lon, opener=run.opener)
            return raw, url, str(year - 1), f'HPMS {year - 1}'
        prior_raw, _ = run.cached('SRC-10', f'hpms2:{_pin_key(lat, lon)}:{year - 1}', None, fetch_prior)
        prior = th.parse_hpms(prior_raw, lat, lon)
    except SourceError:
        pass
    out = []
    for r in roads:
        change = th.traffic_change(r, prior) if prior else {'change_pct': None, 'reason': 'NOT_COVERED'}
        out.append({'label': th.road_label(r), 'aadt': r['aadt'], 'year': r['year'], 'count_year': r.get('count_year'),
            'road_class': th.F_SYSTEM.get(r['f_system']), 'lanes': r['lanes'], 'distance_m': r.get('distance_m'),
            **change})
    data = {'radius_m': th.TRAFFIC_RADIUS_M, 'year': year, 'roads': out,
        'reason': None if out else 'NOT_COVERED',
        'note': 'Annual average daily traffic on the nearest segment of each road; states count most roads every '
            'few years and estimate the years between.'}
    return data, bool(out)


def hazards_section(run, lat, lon):
    def flood(metres):
        raw, snap = run.cached('SRC-11', f'nfhl:{_pin_key(lat, lon)}:{metres}m', 30,
            lambda: (th.fetch_flood(lat, lon, metres, opener=run.opener), th.NFHL_URL, 'current', 'Effective flood maps'))
        return {**th.parse_flood(raw), 'checked': snap.retrieved_at.isoformat()}

    def nri():
        raw, _ = run.cached('SRC-12', f'nri:{_pin_key(lat, lon)}', 90,
            lambda: (th.fetch_nri(lat, lon, opener=run.opener), th.NRI_URL, 'current', 'National Risk Index'))
        return th.parse_nri(raw)

    def sfha_nearby():
        raw, snap = run.cached('SRC-11', f'nfhl-sfha:{_pin_key(lat, lon)}:150m', 30,
            lambda: (th.fetch_flood(lat, lon, 150, opener=run.opener, geometry=True), th.NFHL_URL, 'current',
                'Effective flood maps'))
        return {**th.parse_flood_nearby(raw, lat, lon), 'checked': snap.retrieved_at.isoformat()}

    # Zone at the pin from a ~5 m envelope; high-risk polygons within 150 m decide inside vs nearby.
    at_pin, nearby = _part(lambda: flood(5)), _part(sfha_nearby)
    if nearby.get('reason') is None and nearby.get('distance_m') is not None:
        # The polygon test is authoritative: a 5 m envelope can touch a zone the pin is just outside.
        at_pin = {**at_pin, 'in_sfha': bool(nearby.get('inside'))}
    elif 'value' not in at_pin:  # a failed lookup stays {'value': None, 'reason': ...}
        at_pin = {**at_pin, 'in_sfha': bool(at_pin.get('sfha'))}
    data = {'flood_at_pin': at_pin, 'flood_nearby': nearby, 'nri': _part(nri),
        'disclaimer': 'Screening only, not an official flood determination. Request a FIRMette or survey for decisions.'}
    concerns = []
    if at_pin.get('in_sfha'):
        concerns.append(f"Pin is inside a FEMA high-risk flood zone ({nearby.get('zone') or at_pin['zone']})")
    elif nearby.get('sfha') and (nearby.get('distance_m') is None or nearby['distance_m'] <= 100):
        where = f"about {nearby['distance_m']} m" if nearby.get('distance_m') is not None else 'close to'
        concerns.append(f"FEMA high-risk flood zone {nearby['zone']} {where} from the pin")
    if data['nri'].get('concern'):
        concerns.append(f"National Risk Index rates {', '.join(data['nri']['high_hazards'][:3])} risk high for this tract")
    data['concerns'] = concerns
    return data, any(v.get('reason') is None for v in (at_pin, nearby, data['nri']))


def _overture_snapshot(lat, lon, release):
    """A stored capture for exactly this pin and release (archived seed import or app capture)."""
    for snap in SourceSnapshot.objects.filter(source_id='SRC-13', release=release).order_by('-retrieved_at'):
        c = (snap.context or {}).get('coordinates') or {}
        if round(c.get('lat', 999), 6) == round(lat, 6) and round(c.get('lon', 999), 6) == round(lon, 6) \
                and snap.context.get('radius_miles') == 3:
            return snap
    return None


_COHORT = {}


def _records(store, snap):
    with store.open_verified(snap.artifact_key) as handle:
        return json.loads(handle.read())


def _one_mile_count(records, lat, lon):
    return sum(1 for r in records if biz.countable(r) and biz.CATEGORY_GROUP.get(r.get('basic_category'))
        and haversine_miles(lat, lon, r['lat'], r['lon']) <= 1)


def _cohort_guard(run, prior, latest):
    """docs/04 §5.3: is this release pair a broad data change across monitored pins?"""
    key = (prior, latest)
    if key not in _COHORT:
        pairs = []
        latest_snaps = {}
        for snap in SourceSnapshot.objects.filter(source_id='SRC-13', release=latest):
            c = snap.context.get('coordinates') or {}
            latest_snaps[(round(c.get('lat', 0), 6), round(c.get('lon', 0), 6))] = snap
        for snap in SourceSnapshot.objects.filter(source_id='SRC-13', release=prior):
            c = snap.context.get('coordinates') or {}
            pin = (round(c.get('lat', 0), 6), round(c.get('lon', 0), 6))
            if pin in latest_snaps:
                pairs.append((_one_mile_count(_records(run.store, snap), *pin),
                    _one_mile_count(_records(run.store, latest_snaps[pin]), *pin)))
        _COHORT[key] = (biz.broad_change(pairs), len(pairs))
    return _COHORT[key]


def businesses_section(run, lat, lon, *, location=None, capturer=None):
    capturer = capturer or overture.capture
    try:
        releases = overture.available_releases(opener=run.opener)
    except SourceError as exc:
        log.warning('Overture release listing unavailable (%s); using stored releases', exc.code)
        stored = sorted(set(SourceSnapshot.objects.filter(source_id='SRC-13').values_list('release', flat=True)))
        releases = stored
    if not releases:
        raise SourceError('NOT_COVERED', 'no Overture release available')
    latest, prior = releases[-1], (releases[-2] if len(releases) > 1 else None)

    def load(release, required):
        snap = _overture_snapshot(lat, lon, release)
        if snap is None:
            try:
                payload = capturer(lat, lon, release)
            except SourceError:
                if required:
                    raise
                return None
            snap, _ = publish_snapshot(source_id='SRC-13', scope=f'pin:{_pin_key(lat, lon)}', release=release,
                data_period=f'Overture {release}', source_url=overture.source_url(release), adapter_version=ADAPTER,
                stream=io.BytesIO(payload), store=run.store,
                validation=ValidationReport(True, True, {'columns': overture.COLUMNS}, len(json.loads(payload))),
                context={'coordinates': {'lat': round(lat, 6), 'lon': round(lon, 6)}, 'radius_miles': 3,
                    'attribution_url': 'https://docs.overturemaps.org/attribution/'})
        records = _records(run.store, snap)
        run.snapshots.append(str(snap.pk))
        name, link = SOURCE_META['SRC-13']
        run.sources.setdefault('SRC-13' + release, {'id': 'SRC-13', 'name': name, 'url': link,
            'period': f'Overture release {release}', 'retrieved_at': snap.retrieved_at.isoformat()})
        return records

    current = load(latest, True)
    previous = load(prior, False) if prior else None
    data = {'release': latest, 'prior_release': prior if previous is not None else None,
        **biz.landscape(current, (lat, lon))}
    if previous is None:
        data['changes'] = {'closures': [], 'openings': [], 'reason': 'NOT_ENOUGH_DATA'}
        return data, True
    # Tenant matching happens when alerts are evaluated (signals.candidates), so editing the
    # tenant list never invalidates this section.
    found = biz.changes(previous, current, (lat, lon))
    broad, cohort_size = _cohort_guard(run, prior, latest)
    if broad:
        found['openings'] = []
        for c in found['closures']:
            c['severity'] = 'FYI'
    data['changes'] = {**found, 'closures': found['closures'][:20], 'openings': found['openings'][:20],
        'total_closures': len(found['closures']), 'total_openings': len(found['openings']),
        'broad_data_change': broad, 'cohort_size': cohort_size, 'reason': None}
    return data, True


RING_RADII = {'1/3/5': (1, 3, 5), '3/5/10': (3, 5, 10)}


def jobs_section(run, lat, lon, *, location=None):
    from apps.demographics import geography
    from apps.demographics.service import _geography, DemographicsUnavailable
    radii = RING_RADII[location.ring_preset if location else '1/3/5']
    try:
        from apps.demographics.vintage import current_acs_year
        geo_snap, capture = _geography(lat, lon, max(radii), current_acs_year(), run.store, run.opener)
    except DemographicsUnavailable as exc:
        raise SourceError(exc.code if exc.code in ('SOURCE_ERROR', 'NOT_COVERED') else 'SOURCE_ERROR') from None
    blocks, *_ = geography.parse_geography(capture)
    run.snapshots.append(str(geo_snap.pk))
    run.sources.setdefault('SRC-04', {'id': 'SRC-04', 'name': 'U.S. Census Bureau, 2020 Census blocks (TIGERweb)',
        'url': 'https://tigerweb.geo.census.gov/tigerwebmain/TIGERweb_restmapservice.html',
        'period': '2020 Census blocks', 'retrieved_at': geo_snap.retrieved_at.isoformat()})
    states = sorted({b.geoid[:2] for b in blocks})
    year = min(lodes.latest_year(st, opener=run.opener) for st in states)

    def wac(year):
        combined = {}
        for st in states:
            def fetch(st=st):
                raw, url = lodes.fetch_wac(st, year, opener=run.opener)
                return raw, url, str(year), f'LODES {year} (workplace jobs)'
            raw, _ = run.cached('SRC-05', f'lodes:wac:{st}:{year}', None, fetch)
            combined.update(lodes.parse_wac(raw))
        return combined

    current = lodes.ring_jobs(blocks, wac(year), (lat, lon), radii)
    try:
        prior = lodes.ring_jobs(blocks, wac(year - 1), (lat, lon), radii)
    except SourceError:
        prior = None
    rings = [{'radius_miles': r, **lodes.with_trend(current[r], prior[r] if prior else None)} for r in radii]
    return {'year': year, 'prior_year': year - 1 if prior else None, 'rings': rings,
        'note': 'Jobs by workplace location (all job types). Block-level values carry Census noise; '
            'shown only as ring totals.'}, any(r['total'] > 0 for r in rings)


BUILDERS = {'economy': economy_section, 'traffic': traffic_section, 'hazards': hazards_section,
    'businesses': businesses_section, 'jobs': jobs_section}


def compute_area(location_id, *, sections=SECTIONS, store=None, opener=None, capturer=None):
    store = _store(store)
    location = Location.objects.select_related('current_revision').get(pk=location_id)
    revision = location.current_revision
    if revision is None or revision.lat is None:
        raise SourceError('NOT_PROVIDED', 'Place the pin first')
    version = location.analysis_version
    results = []
    for name in sections:
        run = Run(store, opener)
        try:
            if name == 'businesses':
                data, ok = businesses_section(run, revision.lat, revision.lon, location=location, capturer=capturer)
            elif name == 'jobs':
                data, ok = jobs_section(run, revision.lat, revision.lon, location=location)
            else:
                data, ok = BUILDERS[name](run, revision.lat, revision.lon)
        except SourceError as exc:
            data, ok = {'reason': exc.code}, False
        stale = sorted(k for k, v in run.sources.items() if v.get('stale'))
        key = [name, run.snapshots, stale] + ([SECTION_LOGIC[name]] if name in SECTION_LOGIC else [])
        inputs = hashlib.sha256(json.dumps(key, sort_keys=True).encode()).hexdigest()
        with transaction.atomic():
            if Location.objects.select_for_update().get(pk=location.pk).analysis_version != version:
                raise SourceError('STALE', 'Pin changed during computation')
            try:
                with transaction.atomic():
                    row = AreaSection.objects.create(location=location, revision=revision, analysis_version=version,
                        section=name, status='available' if ok else 'unavailable', data=data,
                        sources=list(run.sources.values()), snapshot_ids=run.snapshots, inputs_sha256=inputs)
            except IntegrityError:
                row = AreaSection.objects.get(location=location, analysis_version=version, section=name,
                    inputs_sha256=inputs)
        results.append(row)
    from apps.insights.signals import safe_evaluate
    safe_evaluate(location.pk)
    return results


def serialize(location):
    placed = location.current_revision_id and location.current_revision.lat is not None
    out = {}
    for name in SECTIONS:
        row = (AreaSection.objects.filter(location=location, analysis_version=location.analysis_version, section=name)
            .order_by('-computed_at').first())
        if row is None:
            stale = AreaSection.objects.filter(location=location, section=name).exists()
            out[name] = {'status': 'not_computed', 'reason': 'NOT_PROVIDED' if not placed else ('STALE' if stale else 'NOT_COMPUTED')}
        else:
            out[name] = {'status': row.status, 'data': row.data, 'sources': row.sources,
                'computed_at': row.computed_at.isoformat(),
                'stale': any(s.get('stale') for s in row.sources)}
    return {'sections': out, 'placed': bool(placed)}
