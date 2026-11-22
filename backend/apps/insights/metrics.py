"""Comparable metrics, portfolio percentiles (MET-20) and the evidence summary (FR-16, FR-26).

All values are read from stored, sourced section results; nothing is recomputed or
estimated here. The standard comparison ring is 3 miles (docs/04 §3.2). Values that
are very-low reliability, not statistically significant (trends), or unavailable
are left out rather than guessed.
"""
from statistics import median

# key -> (label, unit, direction, group). direction: 'up' higher is favourable, 'down' lower is.
METRICS = {
    'population': ('Population within 3 miles', 'people', 'up', 'Trade area'),
    'households': ('Households within 3 miles', 'households', 'up', 'Trade area'),
    'median_household_income': ('Median household income (3 mi)', 'usd', 'up', 'Trade area'),
    'mean_household_income': ('Average household income (3 mi)', 'usd', 'up', 'Trade area'),
    'population_change': ('Population change over 5 years (3 mi)', 'pct', 'up', 'Trade area'),
    'real_income_change': ('Real average income change (3 mi)', 'pct', 'up', 'Trade area'),
    'jobs': ('Jobs located within 3 miles', 'people', 'up', 'Jobs'),
    'jobs_change': ('Change in jobs within 3 miles', 'pct', 'up', 'Jobs'),
    'private_jobs_yoy': ('County private jobs, year over year', 'pct', 'up', 'Economy'),
    'retail_jobs_yoy': ('County retail jobs, year over year', 'pct', 'up', 'Economy'),
    'unemployment_change': ('Unemployment rate change vs a year earlier', 'pts', 'down', 'Economy'),
    'permits_change': ('New homes permitted vs prior 12 months', 'pct', 'up', 'Economy'),
    'aadt': ('Traffic on the main road (vehicles/day)', 'count', 'up', 'Access'),
}
MIN_PORTFOLIO = 5


def _ring(rings, radius=3):
    return next((r for r in rings or [] if r.get('radius_miles') == radius), None)


def refresh_snapshot(location):
    """Rebuild the LocationMetrics row for one location (after evaluation or review)."""
    from .models import LocationMetrics
    from .signals import attention
    values = extract(location, fresh=True)
    values['_list'] = list_numbers(location)
    row, _ = LocationMetrics.objects.update_or_create(location=location, defaults={
        'analysis_version': location.analysis_version, 'values': values, 'attention': attention(location.pk)})
    return row


def list_numbers(location):
    """Properties-list extras (redesign B9): flood status, nearest supermarket, active alerts."""
    from apps.area.models import AreaSection
    from .models import Signal
    from .signals import risk_badges
    rows = {}
    for row in (AreaSection.objects.filter(location=location, analysis_version=location.analysis_version,
            section__in=['hazards', 'businesses']).order_by('computed_at')):
        rows[row.section] = row
    flood = None
    if rows.get('hazards') is not None and rows['hazards'].status == 'available':
        badge = next((b for b in risk_badges(location) if b['kind'] == 'flood'), None)
        flood = badge['level'] if badge else 'none'
    market = None
    biz = rows.get('businesses')
    if biz is not None and biz.status == 'available' and biz.data.get('nearest_supermarket'):
        m = biz.data['nearest_supermarket']
        market = {'name': m.get('brand') or m.get('name'), 'distance_mi': m.get('distance_mi')}
    return {'flood': flood, 'nearest_supermarket': market,
        'active_alerts': Signal.objects.filter(location=location, status='active').count()}


def snapshots(locations):
    """{location id: LocationMetrics} for current rows, rebuilding missing or outdated ones."""
    from .models import LocationMetrics
    locations = list(locations)
    rows = {r.location_id: r for r in LocationMetrics.objects.filter(location__in=locations)}
    out = {}
    for loc in locations:
        row = rows.get(loc.pk)
        if row is None or row.analysis_version != loc.analysis_version:
            row = refresh_snapshot(loc)
        out[loc.pk] = row
    return out


def extract(location, fresh=False):
    """Comparable metric values for one location, each with its source period. Missing keys = unavailable."""
    if not fresh:
        return snapshots([location])[location.pk].values
    from apps.demographics.service import current_result
    from apps.area.models import AreaSection
    out = {}
    demo = current_result(location)
    if demo:
        ring = _ring(demo.rings)
        if ring:
            for key in ('population', 'households', 'median_household_income', 'mean_household_income'):
                m = ring['metrics'].get(key) or {}
                if m.get('value') is not None and m.get('reliability') != 'very_low':
                    out[key] = {'value': m['value'], 'period': demo.data_period, 'source': 'SRC-03',
                        'vintage': demo.acs_year}
            for key, tkey in (('population_change', 'population_change'), ('real_income_change', 'real_mean_income_change')):
                t = (ring.get('trends') or {}).get(tkey) or {}
                if t.get('value') is not None and t.get('significant') is True:
                    out[key] = {'value': t['value'], 'period': t.get('period'), 'source': 'SRC-03',
                        'vintage': demo.acs_year}
    rows = {}
    for row in AreaSection.objects.filter(location=location, analysis_version=location.analysis_version).order_by('computed_at'):
        rows[row.section] = row  # latest wins
    jobs = rows.get('jobs')
    if jobs and jobs.status == 'available':
        ring = _ring(jobs.data.get('rings'))
        if ring:
            out['jobs'] = {'value': ring['total'], 'period': f"LODES {jobs.data['year']}", 'source': 'SRC-05'}
            if ring.get('change_pct') is not None:
                out['jobs_change'] = {'value': ring['change_pct'], 'period': f"{jobs.data['prior_year']}–{jobs.data['year']}", 'source': 'SRC-05'}
    econ = rows.get('economy')
    if econ and econ.status == 'available':
        e = econ.data
        emp = e.get('employment') or {}
        for key, part in (('private_jobs_yoy', 'private'), ('retail_jobs_yoy', 'retail')):
            v = (emp.get(part) or {}).get('yoy_pct')
            if v is not None:
                out[key] = {'value': v, 'period': emp.get('period'), 'source': 'SRC-06'}
        u = e.get('unemployment') or {}
        if u.get('change_pts') is not None:
            out['unemployment_change'] = {'value': u['change_pts'], 'period': u.get('period'), 'source': 'SRC-07'}
        p = e.get('permits') or {}
        if p.get('change_pct') is not None:
            out['permits_change'] = {'value': p['change_pct'], 'period': p.get('period'), 'source': 'SRC-09'}
    traffic = rows.get('traffic')
    if traffic and traffic.status == 'available' and traffic.data.get('roads'):
        road = traffic.data['roads'][0]
        out['aadt'] = {'value': road['aadt'], 'period': f"HPMS {road['year']}", 'source': 'SRC-10', 'detail': road['label']}
    hazards = rows.get('hazards')
    out['_hazards'] = hazards.data if hazards and hazards.status == 'available' else None
    return out


def percentile(value, others):
    """MET-20: share of other owned properties below this value (ties count half)."""
    below = sum(1 for v in others if v < value)
    ties = sum(1 for v in others if v == value)
    return round(100 * (below + 0.5 * ties) / len(others))


def portfolio_values(exclude_id=None):
    from apps.locations.models import Location
    owned = (Location.objects.filter(status='owned').exclude(current_revision__lat__isnull=True)
        .select_related('current_revision'))
    from apps.demographics.vintage import current_acs_year
    year = current_acs_year()
    values = {}
    rows = snapshots(loc for loc in owned if loc.pk != exclude_id)
    for loc in owned:
        if loc.pk == exclude_id:
            continue
        for key, item in rows[loc.pk].values.items():
            # Percentiles compare one ACS vintage only; a property still on the old one is left out.
            if key in METRICS and item.get('vintage', year) == year:
                values.setdefault(key, []).append(item['value'])
    return values, sum(1 for loc in owned if loc.pk != exclude_id)


def benchmarks():
    """Portfolio median and range per metric (for Compare)."""
    values, n = portfolio_values()
    return {k: {'median': median(v), 'min': min(v), 'max': max(v), 'n': len(v)} for k, v in values.items() if v}


def _fmt(key, value):
    unit = METRICS[key][1]
    if unit == 'usd':
        return f'${value:,.0f}'
    if unit == 'pct':
        return f'{value * 100:+.1f}%'
    if unit == 'pts':
        return f'{value:+.1f} pts'
    return f'{value:,.0f}'


def summary(location, signals=()):
    from apps.demographics.vintage import current_acs_year
    current_year = current_acs_year()
    mine = extract(location)
    others, n_owned = portfolio_values(exclude_id=location.pk)
    metrics, strengths, concerns = [], [], []
    for key, (label, unit, direction, group) in METRICS.items():
        item = mine.get(key)
        peer = others.get(key, [])
        entry = {'key': key, 'label': label, 'unit': unit, 'direction': direction, 'group': group,
            'value': None if item is None else item['value'], 'period': item and item.get('period'),
            'source': item and item.get('source'), 'detail': item and item.get('detail'),
            'percentile': None, 'n': len(peer)}
        if item is not None and len(peer) >= MIN_PORTFOLIO and item.get('vintage', current_year) == current_year:
            pct = percentile(item['value'], peer)
            entry['percentile'] = pct
            favourable = pct if direction == 'up' else 100 - pct
            text = f"{label}: {_fmt(key, item['value'])}"
            if favourable >= 75:
                strengths.append({'text': f"{text}, better than {favourable}% of your {len(peer)} properties",
                    'metric': key, 'source': item.get('source'), 'period': item.get('period'), 'weight': favourable})
            elif favourable <= 25:
                concerns.append({'text': f"{text}, weaker than {100 - favourable}% of your {len(peer)} properties",
                    'metric': key, 'source': item.get('source'), 'period': item.get('period'), 'weight': 100 - favourable})
        metrics.append(entry)
    hazard_concerns = []
    hz = mine.get('_hazards')
    if hz:
        for text in hz.get('concerns') or []:
            hazard_concerns.append({'text': text, 'metric': 'hazards', 'source': 'SRC-11' if 'flood zone' in text else 'SRC-12',
                'period': None, 'weight': 200})
    signal_items = [{'text': f"{s['title']} ({s['severity']})", 'metric': 'signal', 'source': s.get('source'),
        'period': s.get('period'), 'weight': 300 if s['severity'] == 'High' else 150}
        for s in signals if s['severity'] in ('High', 'Watch')]
    if any(s.get('rule_id') == 'SIG-11' and s['severity'] in ('High', 'Watch') for s in signals):
        # The flood alert already says it; keep the hazard section's other concerns (NRI).
        hazard_concerns = [c for c in hazard_concerns if c['source'] != 'SRC-11']
    concerns = sorted(signal_items + hazard_concerns + concerns, key=lambda c: -c['weight'])
    strengths.sort(key=lambda c: -c['weight'])
    return {'portfolio_size': n_owned, 'min_portfolio': MIN_PORTFOLIO,
        'benchmark_ready': n_owned >= MIN_PORTFOLIO, 'metrics': metrics,
        'strengths': strengths[:5], 'concerns': concerns[:5],
        'note': 'Compared with the 3-mile ring (or county and road level where that is the metric) of your other owned '
            'properties. Area indicators, not property results.'}
