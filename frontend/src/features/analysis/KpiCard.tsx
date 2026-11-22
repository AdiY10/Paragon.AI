import type { Kpi } from "../../api/types";
import { Stat, type StatChange } from "../../components/ui/Stat";
import { sourceName } from "../../lib/format/sources";
import { distanceMi, formatChangePct, formatIncome, formatInt, rankSentence, rankText } from "../../lib/format/numbers";

/** The headline value of a KPI, or null when it is missing. */
export function kpiValue(kpi: Kpi): string | null {
  if (kpi.unit === "text") return kpi.display ?? null;
  if (kpi.unit === "mi") return kpi.display ?? distanceMi(kpi.value);
  if (kpi.value === null || kpi.value === undefined) return null;
  switch (kpi.unit) {
    case "usd":
      return kpi.display ?? formatIncome(kpi.value);
    case "pct":
      return formatChangePct(kpi.value);
    case "pts":
      return `${kpi.value > 0 ? "+" : kpi.value < 0 ? "−" : ""}${Math.abs(kpi.value).toFixed(1)} pts`;
    default:
      return formatInt(kpi.value);
  }
}

/** Second line under the value (units, distance or road). */
export function kpiSub(kpi: Kpi): string | null {
  if (kpi.unit === "per_day" && kpi.value != null) return `vehicles/day${kpi.detail ? ` on ${kpi.detail}` : ""}`;
  if (kpi.unit === "mi" && kpi.display && kpi.value != null) return `${distanceMi(kpi.value)} away`;
  return kpi.detail ?? null;
}

/**
 * Change line: coloured only when the change is statistically significant and the metric has a good
 * direction (up = good for every ranked KPI); otherwise neutral text.
 */
export function kpiChange(kpi: Kpi): StatChange | null {
  const c = kpi.change;
  if (!c) return null;
  const text =
    (c.unit === "pts" ? `${c.value > 0 ? "+" : c.value < 0 ? "−" : ""}${Math.abs(c.value).toFixed(1)} pts` : formatChangePct(c.value)) +
    (c.since ? ` since ${c.since}` : "") +
    (c.significant === false ? " (not significant)" : "");
  const direction = c.value > 0 ? "up" : c.value < 0 ? "down" : null;
  const good = kpi.direction === "up" ? c.value > 0 : kpi.direction === "down" ? c.value < 0 : null;
  const tone = c.significant === true && good !== null && direction ? (good ? "good" : "bad") : "neutral";
  return { text, tone, direction };
}

/** "4 of 35" (rank), or the legacy percentile wording, or nothing for unranked KPIs. */
export function kpiRank(kpi: Kpi, mode: "property" | "place"): string | null {
  if (kpi.ranked === false) return null;
  if (kpi.rank != null && kpi.of != null) return mode === "place" ? rankSentence(kpi.rank, kpi.of, "place") : rankText(kpi.rank, kpi.of);
  if (kpi.percentile != null && kpi.of != null)
    return `${mode === "place" ? "Would be above" : "Above"} ${kpi.percentile}% of ${kpi.of} owned properties`;
  return null;
}

export function KpiCard({ kpi, mode }: { kpi: Kpi; mode: "property" | "place" }) {
  const rank = kpiRank(kpi, mode);
  const foot = [sourceName(kpi.source), kpi.period].filter(Boolean).join(" · ");
  return (
    <li className="kpi-card">
      <Stat
        label={kpi.label}
        value={kpiValue(kpi)}
        change={kpiChange(kpi)}
        sub={[kpiSub(kpi), rank].filter(Boolean).join(" · ") || undefined}
        footnote={foot || undefined}
      />
    </li>
  );
}

export function KpiGrid({ kpis, mode }: { kpis: Kpi[]; mode: "property" | "place" }) {
  return (
    <ul className="kpi-grid" aria-label="Key numbers">
      {kpis.slice(0, 8).map((kpi) => (
        <KpiCard key={kpi.key} kpi={kpi} mode={mode} />
      ))}
    </ul>
  );
}
