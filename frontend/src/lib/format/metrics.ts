/** Summary metric formatting (moved from Summary.tsx in WI-2). */
export interface SummaryMetric {
  key: string;
  label: string;
  unit: string;
  direction: "up" | "down";
  group: string;
  value: number | null;
  period: string | null;
  source: string | null;
  detail: string | null;
  percentile: number | null;
  n: number;
}

const MINUS = "−";

export function formatMetric(m: Pick<SummaryMetric, "unit" | "value">): string {
  if (m.value === null) return "Unavailable";
  const sign = m.value > 0 ? "+" : m.value < 0 ? MINUS : "";
  switch (m.unit) {
    case "usd":
      return `$${Math.round(m.value).toLocaleString("en-US")}`;
    case "pct":
      return `${sign}${Math.abs(m.value * 100).toFixed(1)}%`;
    case "pts":
      return `${sign}${Math.abs(m.value).toFixed(1)} pts`;
    default:
      return Math.round(m.value).toLocaleString("en-US");
  }
}

/** Position on a 0-100 "favourable" scale: lower-is-better metrics are flipped. */
export function favourable(m: Pick<SummaryMetric, "direction" | "percentile">): number | null {
  if (m.percentile === null) return null;
  return m.direction === "up" ? m.percentile : 100 - m.percentile;
}

export const severityTone = (s: string) => (s === "High" ? "red" : s === "Watch" ? "amber" : "");
