/** Types and pure formatting for ring demographics (GET /api/locations/<id>/demographics/). */
export type Reliability = "high" | "medium" | "low" | "very_low" | null;
export interface Metric {
  metric_id: string;
  value: number | null;
  moe: number | null;
  reliability: Reliability;
  reason: string | null;
  unit: "people" | "households" | "usd" | "share" | null;
  label: string | null;
  open_ended?: boolean;
  display?: string;
  household_coverage?: number;
}
export interface Trend {
  metric_id: string;
  value: number | null;
  reason?: string | null;
  message?: string;
  period?: string;
  adjustment?: string | null;
  current?: number;
  baseline?: number;
  baseline_unadjusted?: number;
  difference?: number;
  difference_moe?: number | null;
  z?: number | null;
  significant?: boolean | null;
  note?: string | null;
}
export interface Ring {
  radius_miles: number;
  metrics: Record<string, Metric>;
  method: {
    apportionment: string;
    blocks_inside: number;
    block_groups: number;
    land_area_weighted_block_groups: number;
    moe_formula: string;
    unresolved_block_groups?: string[];
  };
  trends?: Record<string, Trend>;
  baseline?: { acs_period: string; metrics: Record<string, Metric> };
}
export interface DemographicsSource {
  id: string;
  name: string;
  period: string;
  url: string;
  tables?: string[];
  retrieved_at?: string;
}
export type Demographics =
  | { status: "unavailable"; reason: string; message: string }
  | {
      status: "available";
      ring_preset: string;
      acs_year: number;
      data_period: string;
      computed_at: string;
      pin: { lat: number; lon: number; revision: string };
      rings: Ring[];
      sources: DemographicsSource[];
      trend_baseline: { acs_year: number; cpi_ratio: number } | null;
      caveats: string[];
    };

export const METRIC_ROWS: { key: string; label: string; hint: string }[] = [
  { key: "population", label: "Population", hint: "Residents in the ring" },
  { key: "households", label: "Households", hint: "Occupied housing units" },
  {
    key: "median_household_income",
    label: "Median household income",
    hint: "Interpolated from income brackets",
  },
  {
    key: "mean_household_income",
    label: "Average household income",
    hint: "Total household income ÷ households",
  },
  {
    key: "bachelors_or_higher_share",
    label: "Bachelor's degree or higher",
    hint: "Share of adults 25 and over",
  },
];
export const TREND_ROWS: { key: string; label: string }[] = [
  { key: "population_change", label: "Population change" },
  { key: "real_mean_income_change", label: "Real average income change" },
];

const integer = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 });
const money = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 0,
});

/** Plain-language text for docs/04 §7 reason codes. Never a number. */
export function reasonText(reason: string | null | undefined): string {
  switch (reason) {
    case "SUPPRESSED":
      return "Not published by Census";
    case "NOT_COVERED":
      return "Not covered";
    case "GEOGRAPHY_CHANGED":
      return "Unavailable: census geography changed";
    case "SAME_COUNT":
      return "No new count: the state carried the last count forward";
    case "NOT_ENOUGH_DATA":
      return "Not enough data";
    case "SOURCE_ERROR":
      return "Source unavailable";
    case "NOT_PROVIDED":
      return "Needs a pin";
    case "STALE":
      return "Out of date";
    default:
      return "Unavailable";
  }
}

export function formatValue(metric: Metric | undefined): string {
  if (!metric || metric.value === null) return reasonText(metric?.reason);
  if (metric.display) return metric.display;
  switch (metric.unit) {
    case "usd":
      return money.format(metric.value);
    case "share":
      return `${(metric.value * 100).toFixed(1)}%`;
    default:
      return integer.format(metric.value);
  }
}

export function formatMoe(metric: Metric | undefined): string | null {
  if (!metric || metric.value === null || metric.moe === null) return null;
  if (metric.unit === "usd") return `± ${money.format(metric.moe)}`;
  if (metric.unit === "share") return `± ${(metric.moe * 100).toFixed(1)} pts`;
  return `± ${integer.format(metric.moe)}`;
}

export function reliabilityLabel(r: Reliability): string | null {
  return r === "low"
    ? "Low reliability"
    : r === "very_low"
      ? "Very low reliability"
      : null;
}

export function formatChange(trend: Trend | undefined): string {
  if (!trend || trend.value === null) return reasonText(trend?.reason);
  const pct = trend.value * 100;
  const sign = pct > 0 ? "+" : pct < 0 ? "−" : "";
  return `${sign}${Math.abs(pct).toFixed(1)}%`;
}

/** Significance wording only; colour is reserved for significant changes (docs/05 §6). */
export function significanceText(trend: Trend | undefined): string | null {
  if (!trend || trend.value === null) return null;
  if (trend.significant === true) return "Significant";
  if (trend.significant === false) return "Not significant";
  return "Significance not tested";
}

export function trendTone(trend: Trend | undefined): "up" | "down" | "flat" {
  if (!trend || trend.value === null || trend.significant !== true)
    return "flat";
  return trend.value > 0 ? "up" : "down";
}

export function ringLabel(radius: number) {
  return `${radius} ${radius === 1 ? "mile" : "miles"}`;
}
