import { niceMax, pctOf } from "../../lib/scales";
import { Legend } from "./Legend";

export interface DumbbellRow {
  key: string;
  label: string;
  before: number | null;
  after: number | null;
  beforeDisplay?: string;
  afterDisplay?: string;
  /** Printed change, e.g. "+3.1%". */
  change?: string;
  /** Significance wording, e.g. "Significant". */
  note?: string;
  /** Colour the change only when it is significant and has a good direction. */
  tone?: "good" | "bad" | "neutral";
  reason?: string;
}

/**
 * Before → after on one shared zero-based scale (e.g. ACS 2015–19 → 2020–24). Both values and the
 * change are printed; the hollow dot is "before", the filled accent dot is "after".
 */
export function Dumbbell({
  rows,
  periods,
  label,
  max,
}: {
  rows: DumbbellRow[];
  periods: [string, string];
  label: string;
  max?: number;
}) {
  const scale = max ?? niceMax(Math.max(0, ...rows.flatMap((row) => [row.before ?? 0, row.after ?? 0])));
  return (
    <div className="dumbbell">
      <Legend
        items={[
          { label: periods[0], mark: "before" },
          { label: periods[1], mark: "after" },
        ]}
        label={`${label}: legend`}
      />
      <ul className="dumbbell-list" aria-label={label}>
        {rows.map((row) => {
          const ready = row.before !== null && row.after !== null;
          const a = ready ? pctOf(row.before!, scale) : 0;
          const b = ready ? pctOf(row.after!, scale) : 0;
          return (
            <li key={row.key} className="dumbbell-row">
              <span className="bar-label">{row.label}</span>
              {ready ? (
                <>
                  <span className="dumbbell-track" aria-hidden="true">
                    <span className="dumbbell-link" style={{ left: `${Math.min(a, b)}%`, width: `${Math.abs(b - a)}%` }} />
                    <span className="dumbbell-dot before" style={{ left: `${a}%` }} />
                    <span className="dumbbell-dot after" style={{ left: `${b}%` }} />
                  </span>
                  <span className="dumbbell-values">
                    <span>
                      <span className="sr-only">{periods[0]}: </span>
                      {row.beforeDisplay ?? row.before!.toLocaleString("en-US")}
                    </span>
                    <span aria-hidden="true"> → </span>
                    <span>
                      <span className="sr-only">, {periods[1]}: </span>
                      {row.afterDisplay ?? row.after!.toLocaleString("en-US")}
                    </span>
                    {row.change && (
                      <strong className={`change change-${row.tone ?? "neutral"}`}>
                        <span className="sr-only">, change </span>
                        {row.change}
                      </strong>
                    )}
                    {row.note && <small>{row.note}</small>}
                  </span>
                </>
              ) : (
                <span className="bar-missing">{row.reason ?? "Unavailable"}</span>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
