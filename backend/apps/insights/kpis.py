"""Key numbers, US index and written takeaways for the analysis page (redesign B6b).

Everything here is derived from stored results with fixed templates: no generative text, every
sentence names its metric, value, source and period.
"""
from .metrics import MIN_PORTFOLIO, extract, percentile, portfolio_values

# (key, label, unit, better direction); flood is a status badge, never ranked.
KPI_ORDER = (
    ('population', 'People within 3 mi', 'people', 'up'),
    ('median_household_income', 'Median household income (3 mi)', 'usd', 'up'),
    ('households', 'Households within 3 mi', 'households', 'up'),
    ('jobs', 'Jobs within 3 mi', 'jobs', 'up'),
    ('aadt', 'Main-road traffic per day', 'vehicles', 'up'),
    ('retail_services_1mi', 'Retail and services within 1 mi', 'places', 'up'),
    ('nearest_supermarket_mi', 'Nearest supermarket', 'mi', 'down'),
)
# Ring metrics shown against the nation (100 = US average).
INDEX_METRICS = ('median_household_income', 'median_home_value', 'median_gross_rent', 'bachelors_or_higher_share',
    'median_age', 'households_100k_plus_share', 'owner_occupied_share')


def ordinal(n):
    suffix = 'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')
    return f'{n}{suffix}'


def us_index(value, us_value):
    if value is None or not us_value:
        return None
    return round(100 * value / us_value)


def ring_indexes(rings, acs_year=None):
    """{radius: {metric: index}} against the nation for the same ACS vintage; {} until ingested."""
    from apps.demographics.service import us_reference
    ref = us_reference(acs_year)
    us = (ref or {}).get('US')
    if not us:
        return {}
    return {r['radius_miles']: {k: us_index((r['metrics'].get(k) or {}).get('value'), (us.get(k) or {}).get('value'))
        for k in INDEX_METRICS if (r['metrics'].get(k) or {}).get('value') is not None} for r in rings}


def _rank(value, peer, direction):
    better = sum(1 for v in peer if (v > value if direction == 'up' else v < value))
    return better + 1


def _sections(location):
    from apps.area.models import AreaSection
    rows = {}
    for row in AreaSection.objects.filter(location=location, analysis_version=location.analysis_version).order_by('computed_at'):
        rows[row.section] = row
    return rows


def kpis(location):
    """Fixed-order KPI cards: value, rank "N of M" among owned properties, change where a real
    prior period exists, US index for income, source and period."""
    from apps.demographics.service import current_result
    from .signals import risk_badges
    mine = extract(location)
    owned = location.status == 'owned' and not location.screening
    peer_values, _ = portfolio_values(exclude_id=location.pk)
    demo = current_result(location)
    ring3 = next((r for r in (demo.rings if demo else []) if r.get('radius_miles') == 3), None)
    indexes = ring_indexes([ring3], demo.acs_year).get(3, {}) if ring3 else {}
    rows = _sections(location)
    out = []
    for key, label, unit, direction in KPI_ORDER:
        item = mine.get(key)
        value = None if item is None else item['value']
        if value is not None and unit in ('people', 'households', 'jobs', 'vehicles', 'places'):
            value = round(value)
        card = {'key': key, 'label': label, 'value': value, 'unit': unit,
            'direction': direction, 'rank': None, 'of': None, 'percentile': None, 'hypothetical': not owned,
            'change': None, 'note': None, 'period': item and item.get('period'), 'source': item and item.get('source')}
        peer = peer_values.get(key, [])
        if item is not None and len(peer) >= MIN_PORTFOLIO:
            card.update(rank=_rank(item['value'], peer, direction), of=len(peer) + 1,
                percentile=percentile(item['value'], peer) if direction == 'up' else 100 - percentile(item['value'], peer))
        if key == 'population' and ring3:
            t = (ring3.get('trends') or {}).get('population_change') or {}
            if t.get('value') is not None:
                card['change'] = {'value': t['value'], 'unit': 'pct', 'since': (t.get('period') or '').split(' → ')[0],
                    'significant': bool(t.get('significant'))}
        elif key == 'median_household_income' and indexes.get(key) is not None:
            card['index_vs_us'] = indexes[key]
        elif key == 'jobs' and mine.get('jobs_change'):
            c = mine['jobs_change']
            card['change'] = {'value': c['value'], 'unit': 'pct', 'since': c['period'].split('–')[0], 'significant': None}
        elif key == 'aadt' and rows.get('traffic') is not None and rows['traffic'].data.get('roads'):
            road = rows['traffic'].data['roads'][0]
            card['detail'] = road.get('label')
            if road.get('change_pct') is not None:
                card['change'] = {'value': road['change_pct'], 'unit': 'pct', 'since': str(road.get('prior_year')),
                    'significant': None}
            elif road.get('reason') == 'SAME_COUNT':
                card['note'] = 'Estimate carried forward (no newer count)'
        elif key == 'nearest_supermarket_mi' and item is not None:
            card['detail'] = item.get('detail')
        out.append(card)
    badge = next((b for b in risk_badges(location) if b['kind'] == 'flood'), None)
    hazards = rows.get('hazards')
    out.append({'key': 'flood', 'label': 'Flood status', 'unit': None, 'direction': None, 'rank': None, 'of': None,
        'percentile': None, 'hypothetical': not owned, 'change': None, 'note': None,
        'value': badge['level'] if badge else ('none' if hazards is not None and hazards.status == 'available' else None),
        'detail': badge['label'] if badge else None, 'period': 'Effective flood maps', 'source': 'SRC-11'})
    return out


def _pct(value):
    return f'{value * 100:+.1f}%'.replace('-', '\u2212')


def _fmt(unit, value):
    if unit == 'usd':
        return f'${value:,.0f}'
    if unit == 'mi':
        return f'{value:.1f} mi'
    return f'{value:,.0f}'


def takeaways(location, cards=None, signals=None, limit=5):
    """At most ``limit`` fixed-template sentences with the strongest signal (B6b)."""
    from .signals import active_for, risk_badges
    cards = cards if cards is not None else kpis(location)
    signals = signals if signals is not None else ([] if location.screening else active_for(location))
    by_key = {c['key']: c for c in cards}
    found = []  # (strength, takeaway)

    def add(strength, text, tone, section, source, period):
        found.append((strength, {'text': text, 'tone': tone, 'section': section, 'source': source, 'period': period}))

    for s in signals:
        if s['severity'] == 'High':
            add(90, s['title'], 'caution', 'overview', s.get('source'), s.get('period'))
    for b in risk_badges(location):
        add(70 if b['level'] == 'inside' else 45, b['label'], 'caution', 'risk', b['source'], 'Effective flood maps')
    pop = by_key.get('population')
    if pop and pop['value'] is not None:
        rank = f" — {ordinal(pop['rank'])} of {pop['of']} {'owned ' if not pop['hypothetical'] else ''}properties" \
            if pop['rank'] else ''
        change = pop['change']
        tail = ''
        if change and change['significant']:
            tail = f", {_pct(change['value'])} since {change['since']} (significant)"
        strength = (abs(pop['percentile'] - 50) if pop['percentile'] is not None else 0) + (25 if tail else 0)
        tone = 'positive' if (pop['percentile'] or 50) >= 75 or (change and change['significant'] and change['value'] > 0) \
            else 'caution' if (pop['percentile'] or 50) <= 25 or (change and change['significant'] and change['value'] < 0) \
            else 'neutral'
        add(strength, f"3-mile population {_fmt('people', pop['value'])}{rank}{tail}", tone, 'trade-area', pop['source'], pop['period'])
    inc = by_key.get('median_household_income')
    if inc and inc['value'] is not None and inc.get('index_vs_us') is not None:
        idx = inc['index_vs_us']
        add(abs(idx - 100) / 2, f"Median household income {_fmt('usd', inc['value'])} within 3 mi — {idx} on the US index "
            '(100 = US average)', 'positive' if idx >= 115 else 'caution' if idx <= 85 else 'neutral', 'trade-area',
            inc['source'], inc['period'])
    for key, section in (('jobs', 'daytime'), ('retail_services_1mi', 'retail')):
        card = by_key.get(key)
        if card and card['percentile'] is not None and (card['percentile'] >= 90 or card['percentile'] <= 10):
            add(abs(card['percentile'] - 50), f"{card['label']}: {_fmt(card['unit'], card['value'])} — "
                f"{ordinal(card['rank'])} of {card['of']} properties", 'positive' if card['percentile'] >= 90 else 'caution',
                section, card['source'], card['period'])
    road = by_key.get('aadt')
    if road and road['value'] is not None:
        change = road['change']
        text = f"Main road {road.get('detail') or ''} carries {_fmt('people', road['value'])} vehicles/day ({road['period'].replace('HPMS ', '')})".replace('road  carries', 'road carries')
        if change:
            text += f", {_pct(change['value'])} vs the prior count"
        add(abs(change['value']) * 300 if change else 10, text,
            'caution' if change and change['value'] <= -0.05 else 'neutral', 'access', road['source'], road['period'])
    market = by_key.get('nearest_supermarket_mi')
    if market and market['value'] is not None:
        add(35 if market['value'] > 3 else 20, f"Nearest supermarket: {market.get('detail') or 'a supermarket'}, "
            f"{market['value']:.1f} mi", 'caution' if market['value'] > 3 else 'neutral', 'retail', market['source'],
            market['period'])
    found.sort(key=lambda f: -f[0])
    return [t for _, t in found[:limit]]
