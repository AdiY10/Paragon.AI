/** Scales for the custom charts. Bars always start at 0; nothing extrapolates past the track. */

/** The smallest "nice" number (1, 2, 2.5, 5 × 10^k) at or above `max`. Non-positive → 1. */
export function niceMax(max: number): number {
  if (!Number.isFinite(max) || max <= 0) return 1;
  const exponent = Math.floor(Math.log10(max));
  const base = 10 ** exponent;
  for (const step of [1, 2, 2.5, 5, 10]) {
    const candidate = step * base;
    if (candidate >= max * (1 - 1e-12)) return Number(candidate.toPrecision(12));
  }
  return 10 * base;
}

/** Width of a zero-based bar in percent of the track, clamped to 0–100. */
export function pctOf(value: number, max: number): number {
  if (!Number.isFinite(value) || !Number.isFinite(max) || max <= 0 || value <= 0) return 0;
  return Math.min(100, (value / max) * 100);
}

/** Position (0–100 %) of `value` on a linear [lo, hi] track, clamped. */
export function position(value: number, [lo, hi]: [number, number]): number {
  if (hi <= lo) return 0;
  return Math.min(100, Math.max(0, ((value - lo) / (hi - lo)) * 100));
}

export interface IndexSpan {
  /** Left edge and width of the bar, in percent of the track. */
  left: number;
  width: number;
  /** Where 100 (the US average) sits on the track. */
  center: number;
  direction: "above" | "below" | "equal";
  /** The value ran past the track and was clamped. */
  overflow: "low" | "high" | null;
}

/** A bar diverging from 100 (= US average), clamped to [lo, hi] (default 50–150). */
export function indexSpan(index: number, range: [number, number] = [50, 150]): IndexSpan {
  const [lo, hi] = range;
  const clamped = Math.min(hi, Math.max(lo, index));
  const center = position(100, range);
  const end = position(clamped, range);
  return {
    left: Math.min(center, end),
    width: Math.abs(end - center),
    center,
    direction: index > 100 ? "above" : index < 100 ? "below" : "equal",
    overflow: index < lo ? "low" : index > hi ? "high" : null,
  };
}
