"""Deterministic signal engine (FR-19, FR-20; docs/04 §5).

Signals are derived only from stored section results. Re-evaluating is idempotent:
each (location, rule, subject) has one row that is created, updated, resolved or
expired. Thresholds live in config/signals.yaml.
"""
from datetime import date, timedelta
from pathlib import Path
from django.conf import settings
from django.db import transaction
from django.utils import timezone
import yaml
from .models import Signal

SEVERITY_ORDER = {'High': 0, 'Watch': 1, 'FYI': 2}
CATEGORY_ORDER = ['Tenant', 'Closure', 'Hazard', 'Economy', 'Housing', 'Demographics', 'Traffic', 'Jobs', 'Businesses']
SOURCE_LINKS = {'SRC-03': 'https://www.census.gov/programs-surveys/acs', 'SRC-05': 'https://lehd.ces.census.gov/data/#lodes',
    'SRC-06': 'https://www.bls.gov/cew/', 'SRC-07': 'https://www.bls.gov/lau/', 'SRC-09': 'https://www.census.gov/construction/bps/',
    'SRC-10': 'https://www.fhwa.dot.gov/policyinformation/hpms.cfm', 'SRC-11': 'https://msc.fema.gov/portal/home',
    'SRC-13': 'https://docs.overturemaps.org/attribution/', 'SRC-14': 'https://www.sec.gov/edgar/search/'}


def thresholds():
    return yaml.safe_load((Path(settings.BASE_DIR) / 'config' / 'signals.yaml').read_text())['thresholds']


def _pct(v):
    return f'{v * 100:+.1f}%'


def _candidate(rule, subject, category, severity, direction, title, why, evidence, period, source, event_date=None):
    return {'rule_id': rule, 'subject': subject[:200], 'category': category, 'severity': severity, 'direction': direction,
        'title': title[:300], 'why': why, 'evidence': {**evidence, 'source_link': SOURCE_LINKS.get(source)},
        'period': (period or '')[:120], 'source': source, 'event_date': event_date}


def candidates(location, t=None, today=None):
    """All signals whose conditions currently hold for the location, from stored results."""
    from apps.demographics.service import current_result
    from apps.area.models import AreaSection
    t = t or thresholds()
    out = []
    demo = current_result(location)
    ring = next((r for r in (demo.rings if demo else []) if r.get('radius_miles') == 3), None)
    if ring:
        pop = (ring.get('trends') or {}).get('population_change') or {}
        if pop.get('significant') and abs(pop['value']) >= t['SIG-01']['min_abs_change']:
            neg = pop['value'] < 0
            out.append(_candidate('SIG-01', f'acs:{demo.acs_year}', 'Demographics', 'Watch' if neg else 'FYI',
                'negative' if neg else 'positive', f'3-mile population {_pct(pop["value"])} ({pop["period"]})',
                'Fewer residents within 3 miles can reduce demand for neighborhood retail.' if neg else
                'More residents within 3 miles can increase demand for neighborhood retail.',
                {'baseline': pop.get('baseline'), 'current': pop.get('current'), 'z': pop.get('z'),
                    'threshold': t['SIG-01']['min_abs_change']}, pop.get('period'), 'SRC-03'))
        inc = (ring.get('trends') or {}).get('real_mean_income_change') or {}
        if inc.get('significant') and inc.get('value') is not None:
            c = t['SIG-02']
            if inc['value'] <= c['watch_at_or_below'] or inc['value'] >= c['fyi_at_or_above']:
                neg = inc['value'] < 0
                out.append(_candidate('SIG-02', f'acs:{demo.acs_year}', 'Demographics', 'Watch' if neg else 'FYI',
                    'negative' if neg else 'positive', f'3-mile real average household income {_pct(inc["value"])}',
                    'Household spending power in the trade area has changed after inflation.',
                    {'baseline_inflation_adjusted': inc.get('baseline'), 'current': inc.get('current'), 'z': inc.get('z'), **c},
                    inc.get('period'), 'SRC-03'))
    rows = {}
    for row in AreaSection.objects.filter(location=location, analysis_version=location.analysis_version).order_by('computed_at'):
        rows[row.section] = row
    econ = rows.get('economy')
    if econ and econ.status == 'available':
        e, county = econ.data, (econ.data.get('county') or {}).get('name', 'County')
        emp = e.get('employment') or {}
        priv = (emp.get('private') or {}).get('yoy_pct')
        c = t['SIG-03']
        if priv is not None and (priv <= c['watch_at_or_below'] or priv >= c['fyi_at_or_above']):
            neg = priv < 0
            out.append(_candidate('SIG-03', f'qcew:{emp.get("period")}', 'Economy', 'Watch' if neg else 'FYI',
                'negative' if neg else 'positive', f'{county} private jobs {_pct(priv)} year over year',
                'Local job losses affect household income and daytime traffic.' if neg else
                'Local job gains support household income and daytime traffic.',
                {'value': priv, **c, 'jobs': (emp.get('private') or {}).get('value')}, emp.get('period'), 'SRC-06'))
        retail = (emp.get('retail') or {}).get('yoy_pct')
        if retail is not None and retail <= t['SIG-04']['watch_at_or_below']:
            out.append(_candidate('SIG-04', f'qcew:{emp.get("period")}', 'Economy', 'Watch', 'negative',
                f'{county} retail jobs {_pct(retail)} year over year',
                'Falling retail employment can indicate retail contraction in the county.',
                {'value': retail, **t['SIG-04']}, emp.get('period'), 'SRC-06'))
        u = e.get('unemployment') or {}
        if u.get('change_pts') is not None and u['change_pts'] >= t['SIG-05']['watch_at_or_above_pts']:
            out.append(_candidate('SIG-05', f'laus:{u.get("period")}', 'Economy', 'Watch', 'negative',
                f'{county} unemployment up {u["change_pts"]:.1f} pts to {u["rate"] * 100:.1f}%'
                + (' (preliminary)' if u.get('preliminary') else ''),
                'Rising unemployment can weaken local spending.', {'rate': u.get('rate'), 'prior_rate': u.get('prior_rate'),
                    'change_pts': u['change_pts'], **t['SIG-05']}, u.get('period'), 'SRC-07'))
        p = e.get('permits') or {}
        c = t['SIG-07']
        if p.get('change_pct') is not None and abs(p['change_pct']) >= c['min_abs_pct'] and abs(p.get('change') or 0) >= c['min_abs_units']:
            neg = p['change_pct'] < 0
            out.append(_candidate('SIG-07', f'bps:{p.get("period")}', 'Housing', 'FYI', 'negative' if neg else 'positive',
                f'{county}: {p["value"]:,} new homes permitted, {_pct(p["change_pct"])} vs prior 12 months',
                'New housing adds future households to the trade area.' if not neg else
                'Fewer new homes means slower household growth ahead.',
                {'current': p['value'], 'prior': p.get('prior'), **c}, p.get('period'), 'SRC-09'))
    jobs = rows.get('jobs')
    if jobs and jobs.status == 'available':
        r3 = next((r for r in jobs.data.get('rings', []) if r['radius_miles'] == 3), None)
        c = t['SIG-06']
        if r3 and r3.get('change_pct') is not None and (r3['change_pct'] <= c['watch_at_or_below'] or r3['change_pct'] >= c['fyi_at_or_above']):
            neg = r3['change_pct'] < 0
            out.append(_candidate('SIG-06', f'lodes:{jobs.data["year"]}', 'Jobs', 'Watch' if neg else 'FYI',
                'negative' if neg else 'positive', f'Jobs within 3 miles {_pct(r3["change_pct"])} ({jobs.data["prior_year"]}–{jobs.data["year"]})',
                'Fewer people work near the center, affecting weekday traffic.' if neg else
                'More people work near the center, supporting weekday traffic.',
                {'current': r3['total'], 'prior': r3['prior_total'], **c}, f'LODES {jobs.data["year"]}', 'SRC-05'))
    traffic = rows.get('traffic')
    if traffic and traffic.status == 'available' and traffic.data.get('roads'):
        road = traffic.data['roads'][0]
        c = t['SIG-08']
        if road.get('change_pct') is not None and (road['change_pct'] <= c['watch_at_or_below'] or road['change_pct'] >= c['fyi_at_or_above']):
            neg = road['change_pct'] < 0
            out.append(_candidate('SIG-08', f'hpms:{road["year"]}:{road["label"]}', 'Traffic', 'Watch' if neg else 'FYI',
                'negative' if neg else 'positive', f'Traffic on {road["label"]} {_pct(road["change_pct"])} ({road.get("prior_year")}–{road["year"]})',
                'Traffic past the site affects visibility and convenience trips.',
                {'aadt': road['aadt'], 'prior_aadt': road.get('prior_aadt'), **c}, f'HPMS {road["year"]}', 'SRC-10'))
    hazards = rows.get('hazards')
    if hazards and hazards.status == 'available':
        at, near = hazards.data.get('flood_at_pin') or {}, hazards.data.get('flood_nearby') or {}
        why = ('Special Flood Hazard Areas usually require flood insurance for financed properties and carry higher '
            'physical risk. Screening only, not a flood determination.')
        if at.get('sfha'):
            out.append(_candidate('SIG-11', f'nfhl:pin:{at["zone"]}:{at.get("dfirm_id")}', 'Hazard', 'High', 'negative',
                f'Pin is in FEMA flood zone {at["zone"]} (Special Flood Hazard Area)', why,
                {'zone': at['zone'], 'bfe_ft': at.get('bfe_ft'), 'dfirm_id': at.get('dfirm_id')}, 'Effective flood maps', 'SRC-11'))
        elif near.get('sfha'):
            out.append(_candidate('SIG-11', f'nfhl:near:{near["zone"]}:{near.get("dfirm_id")}', 'Hazard', 'Watch', 'negative',
                f'FEMA flood zone {near["zone"]} within about 100 m of the pin', why,
                {'zone': near['zone'], 'dfirm_id': near.get('dfirm_id')}, 'Effective flood maps', 'SRC-11'))
    biz = rows.get('businesses')
    if biz and biz.status == 'available':
        ch, rel = biz.data.get('changes') or {}, biz.data.get('release')
        for c in ch.get('closures') or []:
            out.append(_candidate('SIG-09', f'overture:{c["id"]}', 'Closure', c['severity'], 'negative',
                f'Possible closure nearby: {c.get("name") or c.get("brand")} ({c["distance_mi"]:.1f} mi)',
                ('Data suggests your tenant\'s location may have closed; confirm with the tenant.' if c.get('tenant_match') else
                 'Possible closure; verify. A nearby anchor or traffic driver closing can reduce shopping trips.'),
                {'overture_id': c['id'], 'evidence': c.get('evidence'), 'distance_mi': c['distance_mi'], 'category': c.get('category'),
                    'release': rel, 'prior_release': biz.data.get('prior_release'), 'lat': c.get('lat'), 'lon': c.get('lon')},
                f'Overture {rel}', 'SRC-13', event_date=_release_date(rel)))
        for c in ch.get('openings') or []:
            out.append(_candidate('SIG-10', f'overture:{c["id"]}', 'Businesses', 'FYI', 'neutral',
                f'New in map data nearby: {c.get("name") or c.get("brand")} ({c["distance_mi"]:.1f} mi)',
                'Newly appears in map data (may be a new opening or a data addition); possible competitor or traffic driver.',
                {'overture_id': c['id'], 'distance_mi': c['distance_mi'], 'category': c.get('category'), 'release': rel},
                f'Overture {rel}', 'SRC-13', event_date=_release_date(rel)))
    out.extend(_tenant_candidates(location, today))
    return out


def _release_date(release):
    try:
        return date.fromisoformat(release[:10])
    except (TypeError, ValueError):
        return None


def _tenant_candidates(location, today=None):
    from .sec import tenant_candidates
    return tenant_candidates(location, today=today)


@transaction.atomic
def evaluate(location, *, today=None):
    """Reconcile stored signals with current conditions. Returns (created, updated, resolved)."""
    t = thresholds()
    today = today or timezone.now().date()
    now = timezone.now()
    found = {(c['rule_id'], c['subject']): c for c in candidates(location, t, today)}
    created = updated = resolved = 0
    existing = {(s.rule_id, s.subject): s for s in Signal.objects.select_for_update().filter(location=location)}
    for key, c in found.items():
        expired = c['event_date'] and c['event_date'] < today - timedelta(days=t['event_days'])
        s = existing.get(key)
        if s is None:
            if expired:
                continue
            Signal.objects.create(location=location, analysis_version=location.analysis_version, **c)
            created += 1
            continue
        if s.status == 'dismissed':
            if SEVERITY_ORDER[c['severity']] < SEVERITY_ORDER[s.severity]:
                s.status = 'active'  # escalation reopens a dismissed signal
            else:
                continue
        changed = s.severity != c['severity'] or s.status != 'active'
        for field in ('severity', 'direction', 'title', 'why', 'evidence', 'period', 'source', 'event_date', 'category'):
            setattr(s, field, c[field])
        s.status = 'expired' if expired else 'active'
        s.resolved_reason = 'older than event window' if expired else ''
        s.analysis_version = location.analysis_version
        s.last_seen_at = now
        if changed:
            s.last_changed_at = now
            updated += 1
        s.save()
    for key, s in existing.items():
        if key not in found and s.status == 'active':
            s.status = 'resolved'
            s.resolved_reason = ('location corrected' if s.analysis_version != location.analysis_version
                else 'condition no longer holds')
            s.last_changed_at = now
            s.save(update_fields=['status', 'resolved_reason', 'last_changed_at'])
            resolved += 1
    return created, updated, resolved


def safe_evaluate(location_id):
    """Called after section computations; never breaks them."""
    from apps.locations.models import Location
    try:
        return evaluate(Location.objects.get(pk=location_id))
    except Exception:
        return None


def serialize(s):
    return {'id': str(s.id), 'rule_id': s.rule_id, 'title': s.title, 'severity': s.severity, 'direction': s.direction,
        'category': s.category, 'why': s.why, 'evidence': s.evidence, 'period': s.period, 'source': s.source,
        'status': s.status, 'detected_at': s.first_detected_at.isoformat(), 'changed_at': s.last_changed_at.isoformat(),
        'location': {'id': str(s.location_id), 'name': s.location.name, 'city': s.location.city, 'state': s.location.state}}


def active_for(location):
    qs = Signal.objects.filter(location=location, status='active').select_related('location')
    return [serialize(s) for s in sorted(qs, key=rank_key)]


def rank_key(s):
    cat = CATEGORY_ORDER.index(s.category) if s.category in CATEGORY_ORDER else 99
    return (SEVERITY_ORDER[s.severity], cat, -s.last_changed_at.timestamp(), s.location.name)


def attention(location_id):
    sev = list(Signal.objects.filter(location_id=location_id, status='active').values_list('severity', flat=True))
    top = min(sev, key=SEVERITY_ORDER.get) if sev else None
    return top if top in ('High', 'Watch') else 'Clear'
