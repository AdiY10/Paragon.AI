"""Statistically qualified trends between non-overlapping ACS vintages (docs/04 §4.1).

MET-06 population change and MET-07 real mean household income change compare
ACS 2015-2019 (2010 geography) with ACS 2020-2024 (2020 geography). Each
vintage is apportioned to the ring with its own geography, so boundary changes
add noise; that is one reason a change must be statistically significant at
90% before anything is flagged.
"""
import math
from .rings import Z90


def trend(metric_id, current, baseline, *, scale=1.0, period, adjustment=None):
    out = {'metric_id': metric_id, 'period': period, 'adjustment': adjustment}
    if current.get('value') is None or baseline.get('value') is None:
        return {**out, 'value': None, 'reason': current.get('reason') or baseline.get('reason') or 'NOT_ENOUGH_DATA'}
    if baseline['value'] <= 0:
        return {**out, 'value': None, 'reason': 'NOT_ENOUGH_DATA'}
    base = baseline['value'] * scale
    base_moe = None if baseline.get('moe') is None else baseline['moe'] * scale
    difference = current['value'] - base
    out.update(current=current['value'], baseline=round(base, 4), baseline_unadjusted=baseline['value'],
        difference=round(difference, 4), value=round(difference / base, 6), reason=None)
    if current.get('moe') is None or base_moe is None:
        return {**out, 'difference_moe': None, 'z': None, 'significant': None,
            'note': 'Margin of error unavailable; significance cannot be tested.'}
    diff_moe = math.sqrt(current['moe'] ** 2 + base_moe ** 2)
    z = abs(difference) / (diff_moe / Z90) if diff_moe > 0 else math.inf
    usable = 'very_low' not in (current.get('reliability'), baseline.get('reliability'))
    return {**out, 'difference_moe': round(diff_moe, 4), 'z': None if math.isinf(z) else round(z, 3),
        'significant': bool(z > Z90) and usable,
        'note': None if usable else 'Very low reliability input; excluded from signals.'}


def ring_trends(current_ring, baseline_ring, cpi_ratio, cpi_label):
    period = '2015–2019 → 2020–2024'
    c, b = current_ring['metrics'], baseline_ring['metrics']
    return {
        'population_change': trend('MET-06', c['population'], b['population'], period=period),
        'real_mean_income_change': trend('MET-07', c['mean_household_income'], b['mean_household_income'],
            scale=cpi_ratio, period=period + ', inflation-adjusted', adjustment=cpi_label),
    }


def unavailable(reason, message):
    return {key: {'metric_id': mid, 'value': None, 'reason': reason, 'message': message}
        for key, mid in (('population_change', 'MET-06'), ('real_mean_income_change', 'MET-07'))}
