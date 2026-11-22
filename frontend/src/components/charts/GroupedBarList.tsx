import { niceMax, pctOf } from "../../lib/scales";
import { Legend } from "./Legend";

export interface GroupedValue {
  value: number | null;
  display?: string;
  reason?: string;
}
export interface GroupedRow {
  key: string;
  label: string;
  /** One value per series, in series order. */
  values: GroupedValue[];
  /** Portfolio median for this row, drawn as a tick on the shared scale. */
  median?: number | null;
  medianDisplay?: string;
}

/**
 * Up to two series per row (accent, then the lighter accent step) on one zero-based scale, with an
 * optional portfolio-median tick. Values are printed beside each bar and the legend names the series.
 */
export function GroupedBarList({
  rows,
  series,
  label,
  max,
  medianLabel = "Portfolio median",
}: {
  rows: GroupedRow[];
  series: [string] | [string, string];
  label: string;
  max?: number;
  medianLabel?: string;
}) {
  const all = rows.flatMap((row) => [...row.values.map((v) => v.value ?? 0), row.median ?? 0]);
  const scale = max ?? niceMax(Math.max(0, ...all));
  const hasMedian = rows.some((row) => row.median != null);
  const legend = [
    ...series.map((name, index) => ({ label: name, mark: (index === 0 ? "a" : "b") as "a" | "b" })),
    ...(hasMedian ? [{ label: medianLabel, mark: "tick" as const }] : []),
  ];
  return (
    <div className="grouped-bars">
      {(series.length > 1 || hasMedian) && <Legend items={legend} label={`${label}: legend`} />}
      <ul className="bar-list grouped" aria-label={label}>
        {rows.map((row) => (
          <li key={row.key} className="grouped-row">
            <span className="bar-label">{row.label}</span>
            <div className="grouped-series">
              {row.values.map((item, index) => (
                <div className="bar-row sub" key={series[index] ?? index}>
                  <span className="sr-only">{series[index]}: </span>
                  {item.value === null ? (
                    <span className="bar-missing">{item.reason ?? "Unavailable"}</span>
                  ) : (
                    <>
                      <span className="bar-track" aria-hidden="true">
                        <span
                          className={index === 0 ? "bar-fill" : "bar-fill bar-fill-b"}
                          style={{ width: `${pctOf(item.value, scale)}%` }}
                        />
                        {row.median != null && index === 0 && (
                          <span className="bar-median" style={{ left: `${pctOf(row.median, scale)}%` }} />
                        )}
                      </span>
                      <span className="bar-value">{item.display ?? item.value.toLocaleString("en-US")}</span>
                    </>
                  )}
                </div>
              ))}
              {row.median != null && (
                <small className="bar-median-note">
                  {medianLabel}: {row.medianDisplay ?? row.median.toLocaleString("en-US")}
                </small>
              )}
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
