"""Ring metrics MET-01..MET-05 from apportioned ACS rows (pure; docs/04 §4)."""
from .rings import (Estimate, weighted_sum, ratio, proportion, interpolated_median,
    reliability, ring_weights, TOP_BRACKET_FLOOR, AGE_LOWER_BOUNDS, HOME_VALUE_LOWER_BOUNDS,
    GROSS_RENT_LOWER_BOUNDS)

METRIC_IDS = {
    'population': 'MET-01', 'households': 'MET-02', 'median_household_income': 'MET-03',
    'mean_household_income': 'MET-04', 'bachelors_or_higher_share': 'MET-05',
}
# Redesign B8: about the area, not the property. Present only when the ACS rows carry the tables.
DEPTH_METRIC_IDS = {
    'households_100k_plus_share': 'MET-30', 'age_under_18_share': 'MET-31', 'age_18_34_share': 'MET-32',
    'age_35_54_share': 'MET-33', 'age_55_64_share': 'MET-34', 'age_65_plus_share': 'MET-35', 'median_age': 'MET-36',
    'owner_occupied_share': 'MET-37', 'median_home_value': 'MET-38', 'median_gross_rent': 'MET-39',
}
AGE_BANDS = {'age_under_18_share': range(3, 7), 'age_18_34_share': range(7, 13), 'age_35_54_share': range(13, 17),
    'age_55_64_share': range(17, 20), 'age_65_plus_share': range(20, 26)}  # B01001 male cells; female = +24


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


def _sum(weights, rows, table, cells):
    """Sum of several cells (each apportioned), MOE as the root of the summed squares."""
    parts = [weighted_sum(weights, rows, f'{table}_{c:03d}') for c in cells]
    missing = next((p for p in parts if not p.available), None)
    if missing is not None:
        return missing
    moes = [p.moe for p in parts]
    return Estimate(sum(p.value for p in parts), None if None in moes else sum(m * m for m in moes) ** 0.5)


def _median(weights, rows, table, cells, bounds, base, unit, top_label):
    brackets = [weighted_sum(weights, rows, f'{table}_{c:03d}') for c in cells]
    missing = next((b for b in brackets if not b.available), None)
    if missing is not None:
        return _out(missing, unit, 'Estimate (interpolated median)')
    value, open_ended = interpolated_median([b.value for b in brackets], bounds)
    out = {'value': None if value is None else round(value, 1 if unit == 'years' else 0),
        'moe': None, 'reliability': reliability(base), 'reason': None if value is not None else 'NOT_ENOUGH_DATA',
        'unit': unit, 'label': 'Estimate (interpolated median)', 'open_ended': open_ended}
    if open_ended:
        out['display'] = top_label
    return out


def depth_metrics(weights, rows):
    """MET-30..39 (redesign B8). Empty when the rows predate the depth tables (e.g. ACS 2015-2019)."""
    out = {}
    households = weighted_sum(weights, rows, 'B19001_001')
    out['households_100k_plus_share'] = _out(proportion(_sum(weights, rows, 'B19001', range(14, 18)), households),
        'share', 'Estimate')
    sample = next(iter(rows.values()), {}) if rows else {}
    if 'B01001_001_E' not in sample:
        return out
    people = weighted_sum(weights, rows, 'B01001_001')
    for key, cells in AGE_BANDS.items():
        out[key] = _out(proportion(_sum(weights, rows, 'B01001', [*cells, *(c + 24 for c in cells)]), people),
            'share', 'Estimate')
    ages = [weighted_sum(weights, rows, f'B01001_{c:03d}') for c in range(3, 26)]
    ages_f = [weighted_sum(weights, rows, f'B01001_{c:03d}') for c in range(27, 50)]
    if all(a.available for a in ages + ages_f):
        value, open_ended = interpolated_median([m.value + f.value for m, f in zip(ages, ages_f)], AGE_LOWER_BOUNDS)
        out['median_age'] = {'value': None if value is None else round(value, 1), 'moe': None,
            'reliability': reliability(people), 'reason': None if value is not None else 'NOT_ENOUGH_DATA',
            'unit': 'years', 'label': 'Estimate (interpolated median)', 'open_ended': open_ended}
    else:
        out['median_age'] = _out(next(a for a in ages + ages_f if not a.available), 'years', 'Estimate (interpolated median)')
    occupied = weighted_sum(weights, rows, 'B25003_001')
    out['owner_occupied_share'] = _out(proportion(weighted_sum(weights, rows, 'B25003_002'), occupied), 'share', 'Estimate')
    out['median_home_value'] = _median(weights, rows, 'B25075', range(2, 28), HOME_VALUE_LOWER_BOUNDS,
        weighted_sum(weights, rows, 'B25075_001'), 'usd', '≥ $2,000,000')
    out['median_gross_rent'] = _median(weights, rows, 'B25063', range(3, 27), GROSS_RENT_LOWER_BOUNDS,
        weighted_sum(weights, rows, 'B25063_002'), 'usd', '≥ $3,500')
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
        **depth_metrics(weights, rows),
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
        for key, metric_id in {**METRIC_IDS, **DEPTH_METRIC_IDS}.items():
            if key in metrics:
                metrics[key]['metric_id'] = metric_id
        results.append({'radius_miles': radius, 'metrics': metrics, 'method': method})
    return results
