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
CATEGORY_ORDER = ['Tenant', 'Closure', 'Competition', 'Hazard', 'Economy', 'Housing', 'Demographics', 'Traffic', 'Jobs', 'Businesses']
SOURCE_LINKS = {'SRC-03': 'https://www.census.gov/programs-surveys/acs', 'SRC-05': 'https://lehd.ces.census.gov/data/#lodes',
    'SRC-06': 'https://www.bls.gov/cew/', 'SRC-07': 'https://www.bls.gov/lau/', 'SRC-09': 'https://www.census.gov/construction/bps/',
    'SRC-10': 'https://www.fhwa.dot.gov/policyinformation/hpms.cfm', 'SRC-11': 'https://msc.fema.gov/portal/home',
    'SRC-13': 'https://docs.overturemaps.org/attribution/', 'SRC-14': 'https://www.sec.gov/edgar/search/'}


def _config():
    return yaml.safe_load((Path(settings.BASE_DIR) / 'config' / 'signals.yaml').read_text())


def thresholds():
    return _config()['thresholds']


def rules():
    """{rule_id: {'enabled': bool, 'next_step': str}} from config/signals.yaml (B7a)."""
    return {k: {'enabled': bool(v.get('enabled')), 'next_step': v.get('next_step', '')}
        for k, v in (_config().get('rules') or {}).items()}


def enabled_rules():
    return {k for k, v in rules().items() if v['enabled']}


def _pct(v):
    return f'{v * 100:+.1f}%'.replace('-', '\u2212')  # a real minus sign in titles


def _candidate(rule, subject, category, severity, direction, title, why, evidence, period, source, event_date=None):
    return {'rule_id': rule, 'subject': subject[:200], 'category': category, 'severity': severity, 'direction': direction,
        'title': title[:300], 'why': why, 'evidence': {**evidence, 'source_link': SOURCE_LINKS.get(source)},
        'period': (period or '')[:120], 'source': source, 'event_date': event_date}


GROCERY_CATEGORIES = {'supermarket', 'grocery_store'}


def candidates(location, t=None, today=None, evaluated=None, out_of_scope=None):
    """High/Watch alerts whose conditions currently hold for the location, from stored results (B7a).

    Alerts are for actionable changes only. Subjects are stable across data periods (docs/04 §5.3):
    a new month updates the same alert rather than raising a new one. ``evaluated`` receives the rule
    ids whose inputs were available, so missing data never resolves an alert; ``out_of_scope``
    receives (rule, subject) keys the old, broader rules would have raised, so their open alerts are
    retired rather than reported as resolved.
    """
    evaluated = set() if evaluated is None else evaluated
    out_of_scope = set() if out_of_scope is None else out_of_scope
    if getattr(location, 'screening', False):
        return []  # new-place analyses are never monitored and never raise alerts (B5)
    from apps.area.models import AreaSection
    t = t or thresholds()
    out = []
    rows = {}
    for row in AreaSection.objects.filter(location=location, analysis_version=location.analysis_version).order_by('computed_at'):
        rows[row.section] = row
    econ = rows.get('economy')
    if econ and econ.status == 'available':
        evaluated.update({'SIG-03', 'SIG-04', 'SIG-05', 'SIG-15'})
        e, county = econ.data, (econ.data.get('county') or {}).get('name', 'County')
        fips = (e.get('county') or {}).get('fips') or county
        emp = e.get('employment') or {}
        priv = (emp.get('private') or {}).get('yoy_pct')
        c = t['SIG-03']
        if priv is not None and priv <= c['watch_at_or_below']:
            out.append(_candidate('SIG-03', f'county:{fips}:private_jobs', 'Economy', 'Watch', 'negative',
                f'{county} private jobs {_pct(priv)} year over year',
                'Local job losses affect household income and daytime traffic.',
                {'value': priv, **c, 'jobs': (emp.get('private') or {}).get('value')}, emp.get('period'), 'SRC-06'))
        retail = (emp.get('retail') or {}).get('yoy_pct')
        if retail is not None and retail <= t['SIG-04']['watch_at_or_below']:
            out.append(_candidate('SIG-04', f'county:{fips}:retail_jobs', 'Economy', 'Watch', 'negative',
                f'{county} retail jobs {_pct(retail)} year over year',
                'Falling retail employment can indicate retail contraction in the county.',
                {'value': retail, **t['SIG-04']}, emp.get('period'), 'SRC-06'))
        u = e.get('unemployment') or {}
        c = t['SIG-05']
        smoothed = 'avg3_change_pts' in u
        change = u.get('avg3_change_pts') if smoothed else u.get('change_pts')
        excess = u.get('excess_vs_state_pts')
        if change is not None and change >= c['watch_at_or_above_pts'] and (
                excess is None or excess >= c['min_excess_vs_state_pts']):
            rate = (u.get('avg3_rate') if smoothed and u.get('avg3_rate') is not None else u['rate']) * 100
            out.append(_candidate('SIG-05', f'county:{fips}:unemployment', 'Economy', 'Watch', 'negative',
                f'{county} unemployment up {change:.1f} pts to {rate:.1f}%'
                + (' (3-month average)' if smoothed else '') + (' (preliminary)' if u.get('preliminary') else ''),
                'Rising unemployment can weaken local spending.' + (
                    f' It rose {excess:.1f} pts more than the state.' if excess is not None else ''),
                {'rate': u.get('rate'), 'three_month_average': u.get('avg3_rate'), 'prior_rate': u.get('prior_rate'),
                    'change_pts': change, 'more_than_state_pts': excess, **c}, u.get('period'), 'SRC-07'))
    if econ and econ.status == 'available' and 'SIG-15' in t:
        out.extend(_county_economy(econ, t['SIG-15'], t['SIG-03'], t['SIG-04'], t['SIG-05']))
    traffic = rows.get('traffic')
    if traffic and traffic.status == 'available':
        evaluated.add('SIG-08')
    if traffic and traffic.status == 'available' and traffic.data.get('roads'):
        road = traffic.data['roads'][0]  # the primary road
        c = t['SIG-08']
        change, prior = road.get('change_pct'), road.get('prior_aadt')
        # change_pct is None when the state carried the same count forward (SAME_COUNT): never an alert.
        years = (road.get('prior_count_year'), road.get('count_year'))
        recent = None not in years and years[1] - years[0] <= c.get('max_count_gap_years', 99)
        span = f'counts {years[0]} → {years[1]}' if None not in years else f'{road.get("prior_year")}–{road["year"]}'
        if change is not None and change <= c['decline_at_or_below'] and (prior or 0) >= c['min_prior_aadt'] and \
                (recent or None in years):
            out.append(_candidate('SIG-08', 'road:primary', 'Traffic', 'Watch', 'negative',
                f'Traffic on {road["label"]} {_pct(change)} ({span})',
                'Fewer vehicles past the site can reduce visibility and convenience trips.',
                {'aadt': road['aadt'], 'prior_aadt': prior, 'count_year': road.get('count_year'),
                    'prior_count_year': road.get('prior_count_year'), **c}, f'HPMS {road["year"]}', 'SRC-10'))
        elif change is not None and abs(change) >= 0.10:
            out_of_scope.add(('SIG-08', 'road:primary'))  # an increase, a minor road, or counts years apart
    biz = rows.get('businesses')
    if biz and biz.status == 'available':
        evaluated.update({'SIG-09', f'overture@{biz.data.get("release")}'})
        ch, rel = biz.data.get('changes') or {}, biz.data.get('release')
        from apps.area.businesses import brand_in, is_key, normalize_brand, ANCHOR_BRANDS, GROCERY_BRANDS
        tenants = {normalize_brand(n) for n in location.tenants.filter(archived=False).values_list('name', flat=True)}
        tenants.discard(None)
        c9 = t['SIG-09']
        for c in ch.get('closures') or []:
            subject = f'place:{c["id"]}'
            if c.get('confirmed') is False:
                continue  # an unconfirmed disappearance is shown in the analysis, not alerted
            label = c.get('brand') or c.get('name')
            own_store = (bool(tenants) and brand_in(label, tenants) and c['distance_mi'] <= c9['tenant_store_within_mi']
                and not ch.get('broad_data_change'))
            # Anchors as the businesses module defines them (key categories or curated anchor brands) plus grocers.
            anchor = (is_key({'basic_category': c.get('category'), 'brand': c.get('brand')}) or brand_in(label, ANCHOR_BRANDS)
                or brand_in(label, GROCERY_BRANDS) or c.get('category') in GROCERY_CATEGORIES) and \
                c['distance_mi'] <= c9['anchor_within_mi']
            if not (own_store or anchor):
                out_of_scope.add(('SIG-09', subject))
                continue
            severity = 'High' if own_store and c.get('evidence') == 'marked permanently closed' else 'Watch'
            out.append(_candidate('SIG-09', subject, 'Closure', severity, 'negative',
                f'Possible closure nearby: {c.get("name") or c.get("brand")} ({c["distance_mi"]:.1f} mi)',
                ("Data suggests your tenant's location may have closed; confirm with the tenant." if own_store else
                 'An anchor or grocery store near the center may have closed; that can reduce shopping trips.'),
                {'overture_id': c['id'], 'evidence': c.get('evidence'), 'distance_mi': c['distance_mi'], 'category': c.get('category'),
                    'tenant_match': own_store, 'release': rel, 'prior_release': biz.data.get('prior_release'),
                    'lat': c.get('lat'), 'lon': c.get('lon')},
                f'Overture {rel}', 'SRC-13', event_date=_release_date(rel)))
    if biz and biz.status == 'available':
        evaluated.add('SIG-14')
        from apps.area.businesses import normalize_brand
        names = location.tenants.filter(archived=False).values_list('name', flat=True)
        out.extend(_competing_grocers(location, biz, {normalize_brand(n) for n in names} - {None}))
    hazards = rows.get('hazards')
    if hazards and hazards.status == 'available':
        evaluated.add('SIG-11')
        out.extend(_flood_zone_change(location, hazards))
    out.extend(_tenant_candidates(location, today))
    evaluated.update({'SIG-12', 'SIG-13'})
    on = rules()
    out = [c for c in out if on.get(c['rule_id'], {}).get('enabled') and c['severity'] in ('High', 'Watch')]
    for c in out:
        c['next_step'] = on[c['rule_id']]['next_step']
    return out


def _county_economy(econ, c15, c03, c04, c05):
    """SIG-15 (B7b): one county alert when at least two of the job/retail/unemployment conditions
    hold, or private jobs fall sharply; replaces three separate county alerts."""
    e = econ.data
    county = (e.get('county') or {}).get('name', 'County')
    fips = (e.get('county') or {}).get('fips') or county
    emp, u = e.get('employment') or {}, e.get('unemployment') or {}
    priv = (emp.get('private') or {}).get('yoy_pct')
    retail = (emp.get('retail') or {}).get('yoy_pct')
    change = u.get('avg3_change_pts') if 'avg3_change_pts' in u else u.get('change_pts')
    excess = u.get('excess_vs_state_pts')
    held = []
    if priv is not None and priv <= c03['watch_at_or_below']:
        held.append(f'private jobs {_pct(priv)} year over year')
    if retail is not None and retail <= c04['watch_at_or_below']:
        held.append(f'retail jobs {_pct(retail)}')
    if change is not None and change >= c05['watch_at_or_above_pts'] and (excess is None or excess >= c05['min_excess_vs_state_pts']):
        held.append(f'unemployment up {change:.1f} pts' + (f' ({excess:.1f} more than the state)' if excess is not None else ''))
    sharp = priv is not None and priv <= c15['private_jobs_sharp_drop']
    if len(held) < c15['min_conditions'] and not sharp:
        return []
    return [_candidate('SIG-15', f'county:{fips}:economy', 'Economy', 'Watch', 'negative',
        f'{county}: local economy weakening ({"; ".join(held)})',
        'Several county indicators point the same way, which can weaken local spending and leasing demand.',
        {'private_jobs_yoy': priv, 'retail_jobs_yoy': retail, 'unemployment_change_pts': change,
            'more_than_state_pts': excess, 'conditions': held, **c15},
        ' · '.join(p for p in (emp.get('period'), u.get('period')) if p), 'SRC-06')]


def _competing_grocers(location, biz, tenants):
    """SIG-14 (B7b): a grocer opened within 2 mi (in the latest two releases, not the one before) and
    the property has a grocer of another brand."""
    from apps.area.businesses import brand_in, normalize_brand, GROCERY_BRANDS
    ours = {t for t in tenants if brand_in(t, GROCERY_BRANDS)}
    if not ours:
        return []
    rel = biz.data.get('release')
    out = []
    for g in (biz.data.get('changes') or {}).get('new_grocers') or []:
        brand = normalize_brand(g.get('brand') or g.get('name'))
        if brand and any(brand_in(brand, {t}) for t in ours):
            continue  # the same brand as our grocer: not a competitor
        out.append(_candidate('SIG-14', f'grocer:{g["id"]}', 'Competition', 'Watch', 'negative',
            f'New competing grocer nearby: {g.get("name") or g.get("brand")} ({g["distance_mi"]:.1f} mi)',
            'A new grocery store within 2 miles competes with your grocery anchor for shopping trips.',
            {'overture_id': g['id'], 'distance_mi': g['distance_mi'], 'category': g.get('category'), 'release': rel,
                'lat': g.get('lat'), 'lon': g.get('lon'), 'our_grocers': sorted(ours)},
            f'Overture {rel}', 'SRC-13', event_date=_release_date(rel)))
    return out


def _flood_zone_change(location, current):
    """SIG-11 (B7b): FEMA's effective map now puts the pin in a high-risk zone it was not in before."""
    from apps.area.models import AreaSection
    previous = (AreaSection.objects.filter(location=location, analysis_version=location.analysis_version,
        section='hazards', status='available', computed_at__lt=current.computed_at).order_by('-computed_at').first())
    if previous is None:
        return []
    def inside(row):
        at = row.data.get('flood_at_pin') or {}
        return bool(at.get('in_sfha', at.get('sfha'))), at.get('zone')
    was, old_zone = inside(previous)
    now, new_zone = inside(current)
    if was or not now:
        return []
    near = current.data.get('flood_nearby') or {}
    zone = near.get('zone') if near.get('inside') else new_zone
    return [_candidate('SIG-11', 'flood:zone_change', 'Hazard', 'High', 'negative',
        f'Flood map change: the pin is now in high-risk zone {zone} (was {old_zone or "outside"})',
        'A revised FEMA flood map can require flood insurance for financed properties and raises physical risk. '
        'Screening only, not a flood determination.',
        {'zone': zone, 'previous_zone': old_zone, 'flood_map_panel': (current.data.get('flood_at_pin') or {}).get('dfirm_id'),
            'base_flood_elevation_ft': (current.data.get('flood_at_pin') or {}).get('bfe_ft')},
        'Effective flood maps', 'SRC-11', event_date=current.computed_at.date())]


def risk_badges(location):
    """Standing risks shown on the analysis, not alerts (B7a): today, inside or near a FEMA high-risk flood zone."""
    from apps.area.models import AreaSection
    row = (AreaSection.objects.filter(location=location, analysis_version=location.analysis_version, section='hazards',
        status='available').order_by('-computed_at').first())
    if row is None:
        return []
    at, near = row.data.get('flood_at_pin') or {}, row.data.get('flood_nearby') or {}
    if at.get('in_sfha', at.get('sfha')):
        zone = near.get('zone') if near.get('inside') else at.get('zone')
        bfe = at.get('bfe_ft')
        return [{'kind': 'flood', 'level': 'inside', 'label': f'Inside FEMA high-risk flood zone {zone}'
            + (f' (base flood elevation {bfe:g} ft)' if isinstance(bfe, (int, float)) else ''), 'source': 'SRC-11'}]
    dist = near.get('distance_m')
    if near.get('sfha') and (dist is None or dist <= 100):
        return [{'kind': 'flood', 'level': 'near', 'label': f'FEMA high-risk flood zone {near.get("zone")} '
            + (f'about {dist} m away' if dist is not None else 'close by'), 'source': 'SRC-11'}]
    return []


def _release_date(release):
    try:
        return date.fromisoformat(release[:10])
    except (TypeError, ValueError):
        return None


def _tenant_candidates(location, today=None):
    from .sec import tenant_candidates
    return tenant_candidates(location, today=today)


EVENT_RULES = {'SIG-09', 'SIG-10', 'SIG-11', 'SIG-12', 'SIG-13', 'SIG-14'}


@transaction.atomic
def evaluate(location, *, today=None):
    """Reconcile stored signals with current conditions. Returns (created, updated, resolved).

    Lifecycle (docs/04 §5.3):
    - one row per (location, rule, subject); new data periods refresh its evidence in place;
    - a dismissal holds until the severity escalates;
    - condition alerts resolve when the condition stops holding, but only if the rule's inputs
      were evaluated this time; a later reappearance starts a new episode;
    - event alerts (closures, openings, filings) stay until ``event_days`` after the event, then expire.
    """
    t = thresholds()
    today = today or timezone.now().date()
    now = timezone.now()
    evaluated, out_of_scope = set(), set()
    found = {(c['rule_id'], c['subject']): c for c in candidates(location, t, today, evaluated, out_of_scope)}
    on = enabled_rules()
    created = updated = resolved = 0
    existing = {(s.rule_id, s.subject): s for s in Signal.objects.select_for_update().filter(location=location)}

    def too_old(event_date):
        return bool(event_date) and event_date < today - timedelta(days=t['event_days'])

    for key, c in found.items():
        expired = too_old(c['event_date'])
        s = existing.get(key)
        if s is None:
            if expired:
                continue
            Signal.objects.create(location=location, analysis_version=location.analysis_version,
                first_evidence=c['evidence'], episode_started_at=now, **c)
            created += 1
            continue
        if s.status == 'dismissed':
            if SEVERITY_ORDER[c['severity']] < SEVERITY_ORDER[s.severity]:
                s.status = 'active'  # escalation reopens a dismissed signal
                s.last_changed_at = now
                updated += 1
            else:
                # Keep the dismissal, but keep the evidence current for anyone who opens it.
                s.evidence, s.period, s.last_seen_at = c['evidence'], c['period'], now
                s.save(update_fields=['evidence', 'period', 'last_seen_at'])
                continue
        reopened = s.status in ('resolved', 'expired', 'retired') and not expired
        changed = s.severity != c['severity'] or reopened
        for field in ('severity', 'direction', 'title', 'why', 'evidence', 'period', 'source', 'event_date', 'category', 'next_step'):
            setattr(s, field, c[field])
        if reopened:
            s.episode += 1
            s.episode_started_at = now
            s.first_evidence = c['evidence']
        s.status = 'expired' if expired else 'active'
        s.resolved_reason = 'older than event window' if expired else ''
        s.analysis_version = location.analysis_version
        s.last_seen_at = now
        if changed:
            s.last_changed_at = now
            updated += 1
        s.save()
    for key, s in existing.items():
        if key in found or s.status in ('resolved', 'expired', 'retired'):
            continue
        if s.rule_id not in on or s.severity == 'FYI' or key in out_of_scope or (
                s.rule_id == 'SIG-11' and s.subject != 'flood:zone_change'):  # the static flood alert is a badge now
            # Outside the alert scope (B7a): retired quietly, never listed as "resolved".
            s.status, s.resolved_reason = 'retired', 'outside the alert scope'
            s.save(update_fields=['status', 'resolved_reason'])
            continue
        if s.status != 'active':
            continue
        moved = s.analysis_version != location.analysis_version
        if moved and s.rule_id not in evaluated:
            s.status, s.resolved_reason = 'resolved', 'location corrected'
        elif s.rule_id in EVENT_RULES and s.event_date and not (
                s.rule_id in ('SIG-09', 'SIG-10') and f'overture@{s.evidence.get("release")}' in evaluated) and \
                s.rule_id not in ('SIG-12', 'SIG-13'):
            # A closure from an earlier release stays listed until it ages out; one that the same
            # release no longer flags (better filtering) resolves. Filings are re-queried each time.
            if too_old(s.event_date):
                s.status, s.resolved_reason = 'expired', 'older than event window'
                s.last_changed_at = now
                s.save(update_fields=['status', 'resolved_reason', 'last_changed_at'])
            continue  # events stay listed until they age out
        elif s.rule_id not in evaluated:
            continue  # inputs unavailable this time: keep the alert rather than guess
        else:
            s.status, s.resolved_reason = 'resolved', 'condition no longer holds'
        s.last_changed_at = now
        s.save(update_fields=['status', 'resolved_reason', 'last_changed_at'])
        resolved += 1
    return created, updated, resolved


def safe_evaluate(location_id):
    """Called after section computations; never breaks them, but always logs failures."""
    import logging
    from apps.locations.models import Location
    try:
        location = Location.objects.select_related('current_revision').get(pk=location_id)
        result = evaluate(location)
        from .metrics import refresh_snapshot
        refresh_snapshot(location)
        return result
    except Exception:
        logging.getLogger(__name__).exception('signal evaluation failed for location %s', location_id)
        return None


def serialize(s):
    return {'id': str(s.id), 'rule_id': s.rule_id, 'title': s.title, 'severity': s.severity, 'direction': s.direction,
        'category': s.category, 'why': s.why, 'evidence': s.evidence, 'period': s.period, 'source': s.source,
        'status': s.status, 'detected_at': s.first_detected_at.isoformat(), 'changed_at': s.last_changed_at.isoformat(),
        'episode': s.episode, 'episode_started_at': (s.episode_started_at or s.first_detected_at).isoformat(),
        'first_evidence': s.first_evidence, 'subject': s.subject,
        'reviewed': s.reviewed_by_id is not None, 'reviewed_at': s.reviewed_at.isoformat() if s.reviewed_at else None,
        'review_note': s.review_note, 'feedback': s.feedback, 'resolved_reason': s.resolved_reason,
        'next_step': s.next_step,
        'location': {'id': str(s.location_id), 'name': s.location.name, 'city': s.location.city, 'state': s.location.state}}


def group_key(s):
    """County figures and one nearby place shared by several properties form one group (B7a)."""
    from .brief import SHARED_SUBJECT_RULES
    return f'{s.rule_id}:{s.subject}' if s.rule_id in SHARED_SUBJECT_RULES else str(s.id)


def group_signals(signals):
    """PART C grouped alerts: one entry per group, worst first, with every property listed."""
    groups, order = {}, []
    for s in sorted(signals, key=rank_key):
        key = group_key(s)
        if key not in groups:
            groups[key] = {'key': key, 'rule_id': s.rule_id, 'title': s.title, 'severity': s.severity,
                'category': s.category, 'why': s.why, 'next_step': s.next_step, 'evidence': s.evidence,
                'period': s.period, 'source': s.source, 'status': s.status, 'locations': [], 'signal_ids': []}
            order.append(key)
        g = groups[key]
        if str(s.location_id) not in {l['id'] for l in g['locations']}:
            g['locations'].append({'id': str(s.location_id), 'name': s.location.name, 'city': s.location.city,
                'state': s.location.state})
        g['signal_ids'].append(str(s.id))
    return [groups[k] for k in order]


def active_for(location):
    qs = Signal.objects.filter(location=location, status='active').select_related('location')
    return [serialize(s) for s in sorted(qs, key=rank_key)]


def rank_key(s):
    cat = CATEGORY_ORDER.index(s.category) if s.category in CATEGORY_ORDER else 99
    return (SEVERITY_ORDER[s.severity], cat, -s.last_changed_at.timestamp(), s.location.name)


COUNTY_ONLY_RULES = {'SIG-03', 'SIG-04', 'SIG-05', 'SIG-07', 'SIG-15'}


def cached_attention(location):
    """Attention from the LocationMetrics snapshot when current (no extra query if prefetched)."""
    from django.core.exceptions import ObjectDoesNotExist
    try:
        row = location.metrics_snapshot
    except ObjectDoesNotExist:
        row = None
    if row is not None and row.analysis_version == location.analysis_version:
        return row.attention
    return attention(location.pk)


def attention(location_id):
    """A property's own attention level. County-wide figures are context, shown in the brief once,
    not a reason to flag every property in the county."""
    sev = list(Signal.objects.filter(location_id=location_id, status='active')
        .exclude(rule_id__in=COUNTY_ONLY_RULES).values_list('severity', flat=True))
    top = min(sev, key=SEVERITY_ORDER.get) if sev else None
    return top if top in ('High', 'Watch') else 'Clear'
