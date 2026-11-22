import type { Kpi } from "../../api/types";
import { Stat, type StatChange } from "../../components/ui/Stat";
import { periodLabel } from "../../lib/format/dates";
import { sourceName } from "../../lib/format/sources";
import { distanceMi, floodShort, formatChangePct, formatIncome, formatInt, rankSentence, rankText } from "../../lib/format/numbers";

const num = (v: Kpi["value"]) => (typeof v === "number" ? v : null);

/** The headline value of a KPI, or null when it is missing. */
export function kpiValue(kpi: Kpi): string | null {
  if (kpi.key === "flood") {
    if (typeof kpi.value === "string") return floodShort(kpi.value as "inside" | "near" | "none") ?? kpi.display ?? null;
    return kpi.display ?? null;
  }
  if (kpi.unit === "text") return kpi.display ?? null;
  const v = num(kpi.value);
  if (kpi.unit === "mi") return kpi.display ?? distanceMi(v);
  if (v === null) return null;
  switch (kpi.unit) {
    case "usd":
      return kpi.display ?? formatIncome(v);
    case "pct":
      return formatChangePct(v);
    case "pts":
      return `${v > 0 ? "+" : v < 0 ? "−" : ""}${Math.abs(v).toFixed(1)} pts`;
    default:
      return formatInt(v);
  }
}

/** Second line under the value: units, road, supermarket name, US index or a note. */
export function kpiSub(kpi: Kpi): string | null {
  const parts: string[] = [];
  const v = num(kpi.value);
  if ((kpi.unit === "per_day" || kpi.unit === "vehicles") && v !== null) parts.push(`vehicles/day${kpi.detail ? ` on ${kpi.detail}` : ""}`);
  else if (kpi.unit === "mi" && kpi.display && v !== null) parts.push(`${distanceMi(v)} away`);
  else if (kpi.key === "flood" && kpi.detail && kpi.value !== "none") parts.push(kpi.detail);
  else if (kpi.detail && kpi.key !== "flood") parts.push(kpi.detail);
  if (kpi.index_vs_us != null) parts.push(`US index ${kpi.index_vs_us} (100 = US average)`);
  if (kpi.note) parts.push(kpi.note);
  return parts.length ? parts.join(" · ") : null;
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
  if (kpi.ranked === false || kpi.key === "flood") return null;
  if (kpi.rank != null && kpi.of != null)
    return mode === "place" || kpi.hypothetical ? rankSentence(kpi.rank, kpi.of, "place") : rankText(kpi.rank, kpi.of);
  if (kpi.percentile != null && kpi.of != null)
    return `${mode === "place" ? "Would be above" : "Above"} ${kpi.percentile}% of ${kpi.of} owned properties`;
  return null;
}

export function KpiCard({ kpi, mode }: { kpi: Kpi; mode: "property" | "place" }) {
  const rank = kpiRank(kpi, mode);
  const foot = [sourceName(kpi.source), periodLabel(kpi.period)].filter(Boolean).join(" · ");
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
