import { useState } from "react";
import { sectionRunState } from "../../../api/analysis";
import type { AnalysisBundle } from "../../../api/types";
import { Dumbbell, type DumbbellRow, IndexBar, IndexScale } from "../../../components/charts";
import { Badge } from "../../../components/ui/Badge";
import { Segmented } from "../../../components/ui/Segmented";
import {
  formatChange,
  formatMoe,
  formatValue,
  DEPTH_ROWS,
  METRIC_ROWS,
  metricLabel,
  reliabilityLabel,
  ringLabel,
  significanceText,
  type Metric,
  type Ring,
  type Trend,
} from "../../../lib/format/demographics";
import { formatInt, formatUsd } from "../../../lib/format/numbers";
import { SectionShell } from "../SectionShell";

type IndexedRing = Ring & { index_vs_us?: Record<string, number | null> };

function MetricCell({ metric }: { metric: Metric | undefined }) {
  const moe = formatMoe(metric);
  const reliability = reliabilityLabel(metric?.reliability ?? null);
  return (
    <td className="num">
      <span className="metric-value">{formatValue(metric)}</span>
      {moe && <small className="moe">{moe}</small>}
      {reliability && (
        <span className="metric-badge">
          <Badge>{reliability}</Badge>
        </span>
      )}
    </td>
  );
}

function trendRow(key: string, label: string, trend: Trend | undefined, unit: "people" | "usd"): DumbbellRow {
  const fmt = (v: number | undefined) => (v === undefined ? undefined : unit === "usd" ? (formatUsd(v) ?? undefined) : (formatInt(v) ?? undefined));
  const significance = significanceText(trend);
  return {
    key,
    label,
    before: trend?.baseline ?? null,
    after: trend?.current ?? null,
    beforeDisplay: fmt(trend?.baseline),
    afterDisplay: fmt(trend?.current),
    change: trend && trend.value !== null ? formatChange(trend) : undefined,
    note: significance ?? undefined,
    tone: trend?.significant === true && trend.value ? (trend.value > 0 ? "good" : "bad") : "neutral",
    reason: trend?.message ?? (trend?.reason ? formatChange(trend) : "No earlier period to compare with"),
  };
}

/** Radius-ring demographics: table with margins of error, US index when present, and 5-year change. */
export function TradeAreaSection({ bundle }: { bundle: AnalysisBundle }) {
  const section = bundle.sections.demographics;
  const data = section.data;
  const rings = (data?.rings ?? []) as IndexedRing[];
  const [radius, setRadius] = useState<number>(rings.find((r) => r.radius_miles === 3) ? 3 : (rings[0]?.radius_miles ?? 3));
  const ring = rings.find((r) => r.radius_miles === radius) ?? rings[0];
  const present = new Set(rings.flatMap((r) => Object.keys(r.metrics)));
  const depthRows = DEPTH_ROWS.filter((row) => present.has(row.key));
  const otherKeys = [...present].filter((key) => ![...METRIC_ROWS, ...DEPTH_ROWS].some((row) => row.key === key));
  const index = ring?.index_vs_us ?? null;
  const indexEntries = index ? Object.entries(index) : [];
  const baselinePeriod = ring?.baseline?.acs_period ?? "Earlier period";
  return (
    <SectionShell
      id="trade-area"
      title="Trade area & demographics"
      run={sectionRunState(section)}
      reason={section.reason}
      stale={section.stale}
      computedAt={section.computed_at}
      sources={section.sources}
      intro={<p>Residents within radius rings around the pin. These describe the area, not this property.</p>}
    >
      {data && (
        <>
          <div className="table-scroll" role="region" aria-labelledby="ring-table-caption" tabIndex={0}>
            <table className="data-table ring-table-v2">
              <caption id="ring-table-caption">Radius rings · {data.data_period}</caption>
              <thead>
                <tr>
                  <th scope="col">Measure</th>
                  {rings.map((r) => (
                    <th scope="col" key={r.radius_miles} className="num">
                      {ringLabel(r.radius_miles)}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {[...METRIC_ROWS, ...depthRows, ...otherKeys.map((key) => ({ key, label: metricLabel(key), hint: "" }))].map((row) => (
                  <tr key={row.key}>
                    <th scope="row">
                      {row.label}
                      {row.hint && <small>{row.hint}</small>}
                    </th>
                    {rings.map((r) => (
                      <MetricCell key={r.radius_miles} metric={r.metrics[row.key]} />
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="fine-print">± values are 90% margins of error. Survey estimates, not counts.</p>
          {rings.length > 1 && (
            <Segmented
              label="Ring"
              options={rings.map((r) => ({ value: String(r.radius_miles), label: `${r.radius_miles} mi` }))}
              value={String(radius)}
              onChange={(value) => setRadius(Number(value))}
            />
          )}
          {indexEntries.length > 0 && (
            <div className="subsection">
              <h3>Compared with the US (100 = US average), {ringLabel(radius)}</h3>
              <div className="index-list">
                {indexEntries.filter(([, value]) => value !== null).map(([key, value]) => (
                  <IndexBar
                    key={key}
                    label={metricLabel(key)}
                    index={value}
                  />
                ))}
                <IndexScale />
              </div>
            </div>
          )}
          <div className="subsection">
            <h3>Change since {baselinePeriod}, {ringLabel(radius)}</h3>
            {section.trends === "running" || section.trends === "pending" ? (
              <p className="fine-print">The earlier-period comparison is still being prepared.</p>
            ) : ring?.trends ? (
              // Each measure gets its own zero-based scale: people and dollars never share an axis.
              <div className="dumbbell-pair">
                <Dumbbell
                  label={`Population change within ${ringLabel(radius)}`}
                  periods={[baselinePeriod, data.data_period]}
                  rows={[trendRow("pop", "Population", ring.trends.population_change, "people")]}
                />
                <Dumbbell
                  label={`Income change within ${ringLabel(radius)}`}
                  periods={[baselinePeriod, data.data_period]}
                  rows={[
                    trendRow("income", "Average household income (inflation-adjusted)", ring.trends.real_mean_income_change, "usd"),
                  ]}
                />
              </div>
            ) : (
              <p className="fine-print">No earlier period is available for this location.</p>
            )}
            <p className="fine-print">Only changes marked significant (90% confidence) should be read as real.</p>
          </div>
        </>
      )}
    </SectionShell>
  );
}
