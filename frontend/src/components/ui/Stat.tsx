import type { ReactNode } from "react";
import { ArrowDownRight, ArrowUpRight } from "lucide-react";

export interface StatChange {
  text: string;
  /** "good"/"bad" only for significant changes on metrics with a good direction; otherwise neutral. */
  tone?: "good" | "bad" | "neutral";
  direction?: "up" | "down" | null;
}

/** Label, value, optional change and footnote. A missing value prints "—" with hidden "Unavailable". */
export function Stat({
  label,
  value,
  change,
  sub,
  footnote,
}: {
  label: string;
  value: string | null;
  change?: StatChange | null;
  sub?: ReactNode;
  footnote?: ReactNode;
}) {
  return (
    <div className="stat-ui">
      <p className="stat-label">{label}</p>
      <p className="stat-value">{value ?? <Missing />}</p>
      {change && (
        <p className={`stat-change change-${change.tone ?? "neutral"}`}>
          {change.direction === "up" && <ArrowUpRight size={14} aria-hidden="true" />}
          {change.direction === "down" && <ArrowDownRight size={14} aria-hidden="true" />}
          {change.text}
        </p>
      )}
      {sub && <p className="stat-sub">{sub}</p>}
      {footnote && <p className="stat-foot">{footnote}</p>}
    </div>
  );
}

/** "—" for a missing number, read as "Unavailable" by screen readers. */
export function Missing({ reason = "Unavailable" }: { reason?: string }) {
  return (
    <>
      <span aria-hidden="true">—</span>
      <span className="sr-only">{reason}</span>
    </>
  );
}
