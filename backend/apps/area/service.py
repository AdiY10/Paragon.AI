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
from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone
from apps.locations.models import Location
from apps.sources.models import SourceSnapshot
from apps.sources.snapshots import publish_snapshot, ValidationReport
from apps.sources.storage import LocalArtifactStore
from . import economy as econ
from . import traffic_hazards as th
from .http import SourceError
from .models import AreaSection

ADAPTER = 'area-v1'
SECTIONS = ('economy', 'traffic', 'hazards')
SOURCE_META = {
    'SRC-04': ('U.S. Census Bureau, TIGERweb counties', 'https://tigerweb.geo.census.gov/tigerwebmain/TIGERweb_restmapservice.html'),
    'SRC-06': ('U.S. Bureau of Labor Statistics, Quarterly Census of Employment and Wages', 'https://www.bls.gov/cew/'),
    'SRC-07': ('U.S. Bureau of Labor Statistics, Local Area Unemployment Statistics', 'https://www.bls.gov/lau/'),
    'SRC-09': ('U.S. Census Bureau, Building Permits Survey', 'https://www.census.gov/construction/bps/'),
    'SRC-10': ('FHWA Highway Performance Monitoring System (USDOT)', 'https://www.fhwa.dot.gov/policyinformation/hpms.cfm'),
    'SRC-11': ('FEMA National Flood Hazard Layer', 'https://www.fema.gov/flood-maps/national-flood-hazard-layer'),
    'SRC-12': ('FEMA National Risk Index', 'https://hazards.fema.gov/nri/'),
}


def _store(store):
    return store or LocalArtifactStore(settings.SOURCE_ARTIFACT_ROOT)


class Run:
    """Collects snapshots and source citations for one section computation."""
    def __init__(self, store, opener):
        self.store, self.opener, self.snapshots, self.sources = store, opener, [], {}

    def cached(self, source_id, scope, max_age_days, fetcher, *, release_match=None):
        """Reuse a fresh snapshot, else fetch, validate and publish. Returns (raw, snapshot)."""
        snap = (SourceSnapshot.objects.filter(source_id=source_id, scope=scope)
            .order_by('-retrieved_at', '-published_at').first())
        fresh = snap and (max_age_days is None or snap.retrieved_at >= timezone.now() - timedelta(days=max_age_days))
        if fresh and (release_match is None or snap.release == release_match):
            with self.store.open_verified(snap.artifact_key) as handle:
                raw = handle.read()
        else:
            raw, url, release, period = fetcher()
            snap, _ = publish_snapshot(source_id=source_id, scope=scope[:160], release=str(release)[:96],
                data_period=period[:160], source_url=url, adapter_version=ADAPTER, stream=io.BytesIO(raw),
                store=self.store, validation=ValidationReport(True, True, {'format': 'raw response'}, 1))
        self.snapshots.append(str(snap.pk))
        name, link = SOURCE_META[source_id]
        self.sources.setdefault(source_id + snap.data_period, {'id': source_id, 'name': name, 'url': link,
            'period': snap.data_period, 'retrieved_at': snap.retrieved_at.isoformat()})
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
    raw, snap = run.cached('SRC-10', f'hpms:{_pin_key(lat, lon)}', 30, latest)
    year = int(snap.release)
    roads = th.primary_roads(th.parse_hpms(raw))
    prior = []
    try:
        def fetch_prior():
            raw, url = th.fetch_hpms(state, year - 1, lat, lon, opener=run.opener)
            return raw, url, str(year - 1), f'HPMS {year - 1}'
        prior_raw, _ = run.cached('SRC-10', f'hpms:{_pin_key(lat, lon)}:{year - 1}', None, fetch_prior)
        prior = th.parse_hpms(prior_raw)
    except SourceError:
        pass
    out = []
    for r in roads:
        change = th.traffic_change(r, prior) if prior else {'change_pct': None, 'reason': 'NOT_COVERED'}
        out.append({'label': th.road_label(r), 'aadt': r['aadt'], 'year': r['year'],
            'road_class': th.F_SYSTEM.get(r['f_system']), 'lanes': r['lanes'], **change})
    data = {'radius_m': th.TRAFFIC_RADIUS_M, 'year': year, 'roads': out,
        'reason': None if out else 'NOT_COVERED',
        'note': 'Annual average daily traffic on the road segment; may be estimated by the state DOT.'}
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

    at_pin, nearby = _part(lambda: flood(30)), _part(lambda: flood(100))
    data = {'flood_at_pin': at_pin, 'flood_nearby': nearby, 'nri': _part(nri),
        'disclaimer': 'Screening only, not an official flood determination. Request a FIRMette or survey for decisions.'}
    concerns = []
    if at_pin.get('sfha'):
        concerns.append(f"Pin is in FEMA zone {at_pin['zone']} (Special Flood Hazard Area)")
    elif nearby.get('sfha'):
        concerns.append(f"FEMA zone {nearby['zone']} (Special Flood Hazard Area) within about 100 m of the pin")
    if data['nri'].get('concern'):
        concerns.append(f"National Risk Index rates this tract {data['nri']['rating']}")
    data['concerns'] = concerns
    return data, any(v.get('reason') is None for v in (at_pin, nearby, data['nri']))


BUILDERS = {'economy': economy_section, 'traffic': traffic_section, 'hazards': hazards_section}


def compute_area(location_id, *, sections=SECTIONS, store=None, opener=None):
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
            data, ok = BUILDERS[name](run, revision.lat, revision.lon)
        except SourceError as exc:
            data, ok = {'reason': exc.code}, False
        inputs = hashlib.sha256(json.dumps([name, run.snapshots], sort_keys=True).encode()).hexdigest()
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
                'computed_at': row.computed_at.isoformat()}
    return {'sections': out, 'placed': bool(placed)}
