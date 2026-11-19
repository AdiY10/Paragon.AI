"""Pure ring-apportionment math for ACS block-group estimates (docs/04 §3.3, §4).

Nothing here performs I/O. Every function either returns a value with its
uncertainty or ``None`` with an explicit reason; it never invents a number.
"""
from dataclasses import dataclass, field
import math

EARTH_RADIUS_MILES = 3958.7613
Z90 = 1.645
# ACS B19001 household-income bracket lower bounds (16 brackets; last is open-ended).
B19001_LOWER_BOUNDS = (0, 10_000, 15_000, 20_000, 25_000, 30_000, 35_000, 40_000,
    45_000, 50_000, 60_000, 75_000, 100_000, 125_000, 150_000, 200_000)
TOP_BRACKET_FLOOR = 200_000


def haversine_miles(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dlat, dlon = p2 - p1, math.radians(lon2 - lon1)
    h = math.sin(dlat / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_MILES * math.asin(math.sqrt(min(1.0, max(0.0, h))))


@dataclass(frozen=True)
class Block:
    geoid: str          # 15-digit 2020 block GEOID (legacy CT county codes)
    population: int     # 2020 decennial POP100
    area_land: int      # square metres
    lat: float          # internal point
    lon: float

    @property
    def block_group(self):
        return self.geoid[:12]


@dataclass(frozen=True)
class BlockGroupTotals:
    population: int
    area_land: int


@dataclass
class RingWeights:
    """Share of each (decennial) block group that lies inside a ring."""
    radius_miles: float
    weights: dict = field(default_factory=dict)   # block-group GEOID -> weight in (0, 1]
    methods: dict = field(default_factory=dict)   # GEOID -> 'population' | 'land_area'
    blocks_inside: int = 0


def ring_weights(center, radius_miles, blocks, bg_totals):
    """Block-population-weighted apportionment (docs/04 §3.3 steps 1-2).

    ``blocks`` must include every block whose internal point may fall inside the
    ring; ``bg_totals`` must cover every block group of those blocks.
    """
    if not (isinstance(radius_miles, (int, float)) and 0 < radius_miles <= 25):
        raise ValueError('Ring radius must be between 0 and 25 miles')
    lat0, lon0 = center
    inside_pop, inside_area, count = {}, {}, 0
    for block in blocks:
        if haversine_miles(lat0, lon0, block.lat, block.lon) <= radius_miles:
            count += 1
            bg = block.block_group
            inside_pop[bg] = inside_pop.get(bg, 0) + block.population
            inside_area[bg] = inside_area.get(bg, 0) + block.area_land
    result = RingWeights(radius_miles=radius_miles, blocks_inside=count)
    for bg in inside_pop:
        totals = bg_totals.get(bg)
        if totals is None:
            raise ValueError(f'Missing 2020 totals for block group {bg}')
        if totals.population > 0:
            weight, method = inside_pop[bg] / totals.population, 'population'
        elif totals.area_land > 0:
            weight, method = inside_area[bg] / totals.area_land, 'land_area'
        else:
            continue
        weight = min(1.0, weight)
        if weight > 0:
            result.weights[bg] = weight
            result.methods[bg] = method
    return result


@dataclass(frozen=True)
class Estimate:
    value: float | None
    moe: float | None          # 90% margin of error; None when not computable
    reason: str | None = None  # reason code when value is None (docs/04 §7)

    @property
    def available(self):
        return self.value is not None


def weighted_sum(weights, rows, column):
    """Σ w·X with MOE = sqrt(Σ (w·MOE)²). Missing inputs make the sum unavailable."""
    total, moe_sq, missing_moe = 0.0, 0.0, False
    for geoid, weight in weights.items():
        row = rows.get(geoid)
        if row is None:
            return Estimate(None, None, 'NOT_COVERED')
        estimate, moe = row.get(f'{column}_E'), row.get(f'{column}_M')
        if estimate is None:
            return Estimate(None, None, 'SUPPRESSED')
        total += weight * estimate
        if moe is None:
            missing_moe = True
        else:
            moe_sq += (weight * moe) ** 2
    return Estimate(total, None if missing_moe else math.sqrt(moe_sq))


def ratio(numerator, denominator):
    """Census ratio approximation: MOE(R) = sqrt(MOE_n² + R²·MOE_d²) / d."""
    if not (numerator.available and denominator.available):
        return Estimate(None, None, numerator.reason or denominator.reason)
    if denominator.value <= 0:
        return Estimate(None, None, 'NOT_ENOUGH_DATA')
    r = numerator.value / denominator.value
    if numerator.moe is None or denominator.moe is None:
        return Estimate(r, None)
    return Estimate(r, math.sqrt(numerator.moe ** 2 + r ** 2 * denominator.moe ** 2) / denominator.value)


def proportion(part, whole):
    """Census proportion approximation, falling back to the ratio formula when the radicand is negative."""
    if not (part.available and whole.available):
        return Estimate(None, None, part.reason or whole.reason)
    if whole.value <= 0:
        return Estimate(None, None, 'NOT_ENOUGH_DATA')
    p = part.value / whole.value
    if part.moe is None or whole.moe is None:
        return Estimate(p, None)
    radicand = part.moe ** 2 - p ** 2 * whole.moe ** 2
    if radicand < 0:
        radicand = part.moe ** 2 + p ** 2 * whole.moe ** 2
    return Estimate(p, math.sqrt(radicand) / whole.value)


def interpolated_median(counts, lower_bounds=B19001_LOWER_BOUNDS):
    """Linear interpolation within the bracket holding the 50th percentile.

    Returns (value, open_ended). ``open_ended`` is True when the median falls in
    the top bracket, in which case only the floor is known ("≥ $200,000").
    """
    if len(counts) != len(lower_bounds):
        raise ValueError('Bracket counts do not match bracket bounds')
    total = sum(counts)
    if total <= 0:
        return None, False
    half, cumulative = total / 2, 0.0
    for index, count in enumerate(counts):
        if cumulative + count >= half and count > 0:
            if index == len(counts) - 1:
                return float(lower_bounds[index]), True
            low, high = lower_bounds[index], lower_bounds[index + 1]
            return low + (half - cumulative) / count * (high - low), False
        cumulative += count
    return None, False


def reliability(estimate):
    """docs/04 §4.2: CV = (MOE/1.645)/estimate."""
    if not estimate.available or estimate.moe is None:
        return None
    if estimate.value == 0:
        return 'very_low' if estimate.moe > 0 else 'high'
    cv = (estimate.moe / Z90) / abs(estimate.value)
    if cv <= 0.15:
        return 'high'
    if cv <= 0.30:
        return 'medium'
    if cv <= 0.40:
        return 'low'
    return 'very_low'
