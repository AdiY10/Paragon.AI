import { ArrowDown, ArrowUp } from "lucide-react";
import { AttentionBadge } from "../../components/ui/Badge";
import { formatMetric } from "../../lib/format/metrics";
import { formatIncome } from "../../lib/format/numbers";

export interface CompareCell {
  value: number | null;
  period: string | null;
  source: string | null;
  detail: string | null;
  best: boolean;
  worst: boolean;
}
export interface CompareRow {
  key: string;
  label: string;
  unit: string;
  direction: "up" | "down" | null;
  group: string;
  cells: Record<string, CompareCell>;
  portfolio: { median: number; min: number; max: number; n: number } | null;
}
export interface CompareColumn {
  id: string;
  name: string;
  city: string;
  state: string;
  status: string;
  screening: boolean;
  attention: "High" | "Watch" | "Clear" | string;
  flood_zone: string | null;
  sfha: boolean;
  nri_rating: string | null;
  signals: { title: string; severity: string }[];
}
export interface CompareData {
  locations: CompareColumn[];
  rows: CompareRow[];
  note: string;
}

/** Median income at the ACS top bracket is a floor ("≥ $200,000"), never an exact figure. */
const value = (unit: string, v: number | null, key = "") =>
  key === "median_household_income" ? (formatIncome(v) ?? "Unavailable") : formatMetric({ unit, value: v });

/** Side-by-side table: sticky first column; strongest/weakest marked with an icon + text, only on rows with a direction. */
export function CompareTable({ data }: { data: CompareData }) {
  const groups = [...new Set(data.rows.map((r) => r.group))];
  const cols = data.locations;
  return (
    <div className="table-scroll compare-scroll" role="region" aria-labelledby="compare-caption" tabIndex={0}>
      <table className="data-table compare-table-v2">
        <caption id="compare-caption">Side-by-side comparison</caption>
        <thead>
          <tr>
            <th scope="col" className="sticky-col">
              Measure
            </th>
            {cols.map((l) => (
              <th scope="col" key={l.id}>
                <a href={(l.screening ? "#/analyze/" : "#/p/") + l.id}>{l.name}</a>
                <small>
                  {[l.city, l.state].filter(Boolean).join(", ")}
                  {l.screening ? " · new place" : ""}
                </small>
                {!l.screening && (l.attention === "High" || l.attention === "Watch") && (
                  <span className="compare-attention">
                    <AttentionBadge level={l.attention} />
                  </span>
                )}
              </th>
            ))}
            <th scope="col">Portfolio median (range)</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <th scope="row" className="sticky-col">
              Flood zone at the pin
            </th>
            {cols.map((l) => (
              <td key={l.id}>
                <strong>{l.flood_zone ?? "—"}</strong>
                {l.flood_zone === null && <span className="sr-only">Unavailable</span>}
                {l.sfha && <small>High-risk zone</small>}
              </td>
            ))}
            <td>
              <small>Not compared</small>
            </td>
          </tr>
          <tr>
            <th scope="row" className="sticky-col">
              National Risk Index
            </th>
            {cols.map((l) => (
              <td key={l.id}>{l.nri_rating ?? "—"}</td>
            ))}
            <td>
              <small>Not compared</small>
            </td>
          </tr>
        </tbody>
        {groups.map((g) => (
          <tbody key={g}>
            <tr>
              <th scope="colgroup" colSpan={cols.length + 2} className="group-row sticky-col">
                {g}
              </th>
            </tr>
            {data.rows
              .filter((r) => r.group === g)
              .map((r) => (
                <tr key={r.key}>
                  <th scope="row" className="sticky-col">
                    {r.label}
                  </th>
                  {cols.map((l) => {
                    const c = r.cells[l.id];
                    const marked = r.direction && c?.value !== null;
                    return (
                      <td key={l.id} className="num">
                        <strong>{c ? value(r.unit, c.value, r.key) : "Unavailable"}</strong>
                        {marked && c.best && (
                          <span className="rank-mark best">
                            <ArrowUp size={12} aria-hidden="true" /> Strongest
                          </span>
                        )}
                        {marked && c.worst && (
                          <span className="rank-mark worst">
                            <ArrowDown size={12} aria-hidden="true" /> Weakest
                          </span>
                        )}
                        {c?.period && <small>{c.period}</small>}
                      </td>
                    );
                  })}
                  <td className="num">
                    {r.portfolio ? (
                      <>
                        <strong>{value(r.unit, r.portfolio.median, r.key)}</strong>
                        <small>
                          {value(r.unit, r.portfolio.min, r.key)} to {value(r.unit, r.portfolio.max, r.key)} ·{" "}
                          {r.portfolio.n} properties
                        </small>
                      </>
                    ) : (
                      <small>No portfolio data</small>
                    )}
                  </td>
                </tr>
              ))}
          </tbody>
        ))}
      </table>
    </div>
  );
}
