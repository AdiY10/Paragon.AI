"""Ring metrics MET-01..MET-05 from apportioned ACS rows (pure; docs/04 §4)."""
from .rings import (Estimate, weighted_sum, ratio, proportion, interpolated_median,
    reliability, ring_weights, TOP_BRACKET_FLOOR)

METRIC_IDS = {
    'population': 'MET-01', 'households': 'MET-02', 'median_household_income': 'MET-03',
    'mean_household_income': 'MET-04', 'bachelors_or_higher_share': 'MET-05',
}


def _out(estimate, unit, label):
    return {'value': None if estimate.value is None else round(estimate.value, 4),
        'moe': None if estimate.moe is None else round(estimate.moe, 4),
        'reliability': reliability(estimate), 'reason': estimate.reason,
        'unit': unit, 'label': label}


def acs_weights(weights_2020, mapping, unresolved):
    """Translate 2020 block-group weights to ACS GEOIDs; fail closed on unresolved ones."""
    blocked = [bg for bg in weights_2020 if bg in unresolved]
    if blocked:
        return None, blocked
    out = {}
    for bg, weight in weights_2020.items():
        geoid = mapping[bg]
        out[geoid] = out.get(geoid, 0.0) + weight
    return out, []


MIN_INCOME_COVERAGE = 0.95


def _mean_income(weights, rows, households):
    """Mean HH income over block groups where Census publishes aggregate income.

    Census omits B19025 for some tiny block groups. They are excluded from both
    numerator and denominator; if they hold more than 5% of the ring's
    households the metric is withheld rather than biased.
    """
    published = {g: w for g, w in weights.items()
        if rows.get(g, {}).get('B19025_001_E') is not None}
    covered = weighted_sum(published, rows, 'B11001_001')
    if not (households.available and covered.available) or households.value <= 0:
        return _out(Estimate(None, None, households.reason or 'NOT_ENOUGH_DATA'), 'usd', 'Estimate')
    coverage = covered.value / households.value
    if coverage < MIN_INCOME_COVERAGE:
        out = _out(Estimate(None, None, 'SUPPRESSED'), 'usd', 'Estimate')
    else:
        out = _out(ratio(weighted_sum(published, rows, 'B19025_001'), covered), 'usd', 'Estimate')
    out['household_coverage'] = round(coverage, 4)
    return out


def ring_metrics(weights, rows):
    population = weighted_sum(weights, rows, 'B01003_001')
    households = weighted_sum(weights, rows, 'B11001_001')
    adults_25 = weighted_sum(weights, rows, 'B15003_001')
    degree_parts = [weighted_sum(weights, rows, f'B15003_{c}') for c in ('022', '023', '024', '025')]
    if all(p.available for p in degree_parts):
        moes = [p.moe for p in degree_parts]
        degrees = Estimate(sum(p.value for p in degree_parts),
            None if None in moes else sum(m * m for m in moes) ** 0.5)
    else:
        degrees = next(p for p in degree_parts if not p.available)
    brackets = [weighted_sum(weights, rows, f'B19001_{i:03d}') for i in range(2, 18)]
    if all(b.available for b in brackets):
        median, open_ended = interpolated_median([b.value for b in brackets])
        median_out = {'value': None if median is None else round(median),
            'moe': None, 'reliability': reliability(households),
            'reason': None if median is not None else 'NOT_ENOUGH_DATA',
            'unit': 'usd', 'label': 'Estimate (interpolated median)',
            'open_ended': open_ended}
        if open_ended:
            median_out['display'] = f'≥ ${TOP_BRACKET_FLOOR:,}'
    else:
        median_out = _out(next(b for b in brackets if not b.available), 'usd', 'Estimate (interpolated median)')
    return {
        'population': _out(population, 'people', 'Estimate'),
        'households': _out(households, 'households', 'Estimate'),
        'median_household_income': median_out,
        'mean_household_income': _mean_income(weights, rows, households),
        'bachelors_or_higher_share': _out(proportion(degrees, adults_25), 'share', 'Estimate'),
    }


def compute_rings(center, radii, blocks, totals, mapping, unresolved, rows):
    """Return one result per radius with metrics plus the method evidence for each."""
    results = []
    for radius in radii:
        weights = ring_weights(center, radius, blocks, totals)
        translated, blocked = acs_weights(weights.weights, mapping, unresolved)
        method = {'apportionment': 'decennial block-population weights (2020 Census blocks)',
            'blocks_inside': weights.blocks_inside, 'block_groups': len(weights.weights),
            'land_area_weighted_block_groups': sum(1 for m in weights.methods.values() if m == 'land_area'),
            'moe_formula': 'sqrt(sum((w*MOE)^2)); Census ratio/proportion approximations'}
        if translated is None:
            metrics = {key: {'value': None, 'moe': None, 'reliability': None,
                'reason': 'GEOGRAPHY_CHANGED', 'unit': None, 'label': None} for key in METRIC_IDS}
            method['unresolved_block_groups'] = sorted(blocked)
        else:
            metrics = ring_metrics(translated, rows)
        for key, metric_id in METRIC_IDS.items():
            metrics[key]['metric_id'] = metric_id
        results.append({'radius_miles': radius, 'metrics': metrics, 'method': method})
    return results
