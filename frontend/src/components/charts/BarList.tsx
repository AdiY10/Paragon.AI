import { niceMax, pctOf } from "../../lib/scales";

export interface BarItem {
  key: string;
  label: string;
  /** null = unavailable: the row prints `reason` and draws no bar. */
  value: number | null;
  /** Printed value; defaults to the plain number. */
  display?: string;
  reason?: string;
  /** Secondary line under the label (e.g. "1.2 mi"). */
  note?: string;
}

/**
 * Horizontal bars from a shared zero baseline, one series. Every value is printed as text; the bar
 * is decoration (aria-hidden), so the list reads as "label, value".
 */
export function BarList({
  items,
  label,
  max,
  className = "",
}: {
  items: BarItem[];
  /** Accessible name of the list, e.g. "Jobs by sector within 3 miles". */
  label: string;
  /** Shared scale maximum (e.g. across rings); defaults to a nice max of these values. */
  max?: number;
  className?: string;
}) {
  const scale = max ?? niceMax(Math.max(0, ...items.map((item) => item.value ?? 0)));
  return (
    <ul className={`bar-list ${className}`.trim()} aria-label={label}>
      {items.map((item) => (
        <li key={item.key} className="bar-row">
          <span className="bar-label">
            {item.label}
            {item.note && <small>{item.note}</small>}
          </span>
          {item.value === null ? (
            <span className="bar-missing">{item.reason ?? "Unavailable"}</span>
          ) : (
            <>
              <span className="bar-track" aria-hidden="true">
                <span className="bar-fill" style={{ width: `${pctOf(item.value, scale)}%` }} />
              </span>
              <span className="bar-value">{item.display ?? item.value.toLocaleString("en-US")}</span>
            </>
          )}
        </li>
      ))}
    </ul>
  );
}
