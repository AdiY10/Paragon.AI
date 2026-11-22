import { useState } from "react";
import { Star } from "lucide-react";
import { useAnalyses, useKeepAnalysis } from "../../api/hooks";
import type { AnalysisListItem, AnalysisState } from "../../api/types";
import { ErrorState } from "../../components/ui/ErrorState";
import { LiveRegion } from "../../components/ui/LiveRegion";
import { Skeleton } from "../../components/ui/Skeleton";
import { dateLabel } from "../../lib/format/dates";

const STATE_TEXT: Record<AnalysisState, string> = {
  complete: "Ready",
  partial: "Partly ready",
  running: "Analyzing",
  queued: "Queued",
  failed: "Could not finish",
  unplaced: "Needs a pin",
};

export const stateText = (state: AnalysisState) => STATE_TEXT[state] ?? state;

/** History of analyzed places, newest first; a star keeps one beyond 90 days. */
export function RecentAnalyses() {
  const list = useAnalyses();
  const keep = useKeepAnalysis();
  const [message, setMessage] = useState("");
  const rows: AnalysisListItem[] = list.data ?? [];
  return (
    <section className="recent-analyses" aria-labelledby="recent-title">
      <h2 id="recent-title">Recent analyses</h2>
      <p className="fine-print">Kept for 90 days unless starred. New places are never monitored and never create alerts.</p>
      {list.error ? (
        <ErrorState error={list.error} title="Recent analyses could not load." onRetry={() => void list.refetch()} />
      ) : !list.data ? (
        <Skeleton lines={3} height={36} />
      ) : rows.length === 0 ? (
        <p className="fine-print">No places analyzed yet.</p>
      ) : (
        <ul className="recent-list">
          {rows.map((row) => (
            <li key={row.id}>
              <div className="recent-main">
                <a href={"#/analyze/" + row.id}>{row.display_label || row.name}</a>
                <small>
                  {dateLabel(row.created_at)}
                  {!row.kept && row.expires_at ? ` · removed after ${dateLabel(row.expires_at)}` : ""}
                </small>
              </div>
              <span className={`state-chip state-${row.state}`}>{stateText(row.state)}</span>
              <button
                type="button"
                className="star-button"
                aria-pressed={row.kept}
                aria-label={`Keep ${row.display_label || row.name}`}
                onClick={() =>
                  keep.mutate(
                    { id: row.id, kept: !row.kept },
                    {
                      onSuccess: (r) => setMessage(r.kept ? `${row.name} is kept.` : `${row.name} is no longer starred.`),
                      onError: (e) => setMessage(e instanceof Error ? e.message : "Could not change the star."),
                    },
                  )
                }
              >
                <Star size={16} aria-hidden="true" fill={row.kept ? "currentColor" : "none"} />
              </button>
            </li>
          ))}
        </ul>
      )}
      <LiveRegion message={message} />
    </section>
  );
}
