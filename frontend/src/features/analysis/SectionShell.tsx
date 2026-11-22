import type { ReactNode } from "react";
import { AlertCircle, Clock } from "lucide-react";
import { sectionReasonText, type RunState } from "../../api/analysis";
import type { SourceRef } from "../../api/types";
import { Skeleton } from "../../components/ui/Skeleton";
import { dateLabel } from "../../lib/format/dates";
import type { SectionId } from "./sections";

/** Section names shown to people for the source catalogue ids. */
export function sourceLine(sources: SourceRef[]) {
  const names = [...new Set(sources.map((s) => s.name))];
  return names.join(" · ");
}
function latest(dates: (string | null | undefined)[]) {
  const valid = dates.filter((d): d is string => !!d).sort();
  return valid.length ? valid[valid.length - 1] : null;
}

/**
 * One analysis section: an h2-labelled region; while its data is still coming in it is aria-busy
 * with a skeleton sized like the final layout; a failure shows a plain-language reason and never
 * blanks the page; a stale note is neutral; the footer names the sources and when they were checked.
 */
export function SectionShell({
  id,
  title,
  run,
  reason,
  stale,
  computedAt,
  sources = [],
  skeleton,
  intro,
  children,
}: {
  id: SectionId;
  title: string;
  run: RunState;
  reason?: string | null;
  stale?: boolean;
  computedAt?: string | null;
  sources?: SourceRef[];
  /** Placeholder with the final layout's size. */
  skeleton?: ReactNode;
  intro?: ReactNode;
  children?: ReactNode;
}) {
  const checked = latest([computedAt, ...sources.map((s) => s.checked_at ?? s.retrieved_at)]);
  return (
    <section id={id} className="analysis-section" aria-labelledby={id + "-title"} aria-busy={run === "loading"}>
      <h2 id={id + "-title"}>{title}</h2>
      {intro && <div className="section-intro">{intro}</div>}
      {run === "loading" ? (
        <div className="section-loading">
          <p className="section-loading-text">Gathering public data for this section…</p>
          {skeleton ?? <Skeleton lines={4} height={18} />}
        </div>
      ) : run === "unavailable" ? (
        <p className="section-unavailable">
          <AlertCircle size={16} aria-hidden="true" />
          <span>{sectionReasonText(reason)}</span>
        </p>
      ) : (
        <>
          {stale && (
            <p className="section-stale">
              <Clock size={14} aria-hidden="true" /> Last good figures shown; the source could not be refreshed on its
              usual schedule.
            </p>
          )}
          {children}
        </>
      )}
      {(sources.length > 0 || checked) && run !== "loading" && (
        <p className="section-sources">
          Sources{sources.length ? `: ${sourceLine(sources)}` : ""}
          {checked ? ` · checked ${dateLabel(checked)}` : ""}
        </p>
      )}
    </section>
  );
}
