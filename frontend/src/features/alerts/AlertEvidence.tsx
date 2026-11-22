import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ThumbsDown, ThumbsUp } from "lucide-react";
import { api } from "../../api/client";
import { Button } from "../../components/ui/Button";
import { Drawer } from "../../components/ui/Drawer";
import { dateLabel } from "../../lib/format/dates";
import { GLOSSARY, RULE_NAMES, evidenceRows } from "./alertText";

export interface AlertLike {
  id: string;
  rule_id: string;
  title: string;
  severity: "High" | "Watch" | "FYI";
  why: string;
  period?: string | null;
  source?: string | null;
  evidence?: Record<string, unknown>;
  status?: string;
  reviewed?: boolean;
  reviewed_at?: string | null;
  review_note?: string;
  feedback?: string;
  detected_at?: string;
  location?: { id: string; name: string; city?: string; state?: string };
  next_step?: string | null;
}

const SOURCE_TERMS: Record<string, string[]> = {
  "SRC-03": ["ACS", "CPI"],
  "SRC-05": ["LODES"],
  "SRC-06": ["QCEW"],
  "SRC-07": ["LAUS"],
  "SRC-10": ["HPMS"],
  "SRC-11": ["High-risk flood zone"],
  "SRC-12": ["NRI"],
  "SRC-14": ["CIK"],
};

/** Review, dismiss (with a note), reopen, and "was this useful?" for one alert. */
export function AlertActions({
  alert,
  compact = false,
  applyToGroup = false,
}: {
  alert: AlertLike;
  compact?: boolean;
  /** A shared alert (county figure, one nearby place): the review applies to every property's copy. */
  applyToGroup?: boolean;
}) {
  const cache = useQueryClient();
  const [note, setNote] = useState(alert.review_note ?? "");
  const [noting, setNoting] = useState(false);
  const [state, setState] = useState({ status: alert.status, reviewed: alert.reviewed, feedback: alert.feedback });
  const review = useMutation({
    mutationFn: (body: Record<string, string>) =>
      api<AlertLike>(`/api/signals/${alert.id}/review/`, "POST", applyToGroup ? { ...body, apply_to_group: true } : body),
    onSuccess: (s) => {
      setState({ status: s.status, reviewed: s.reviewed, feedback: s.feedback });
      setNoting(false);
      // Reviews change attention: refresh alerts, analyses and the property list.
      for (const key of ["signals", "analysis", "summary", "locations", "location"]) cache.invalidateQueries({ queryKey: [key] });
    },
  });
  const dismissed = state.status === "dismissed";
  return (
    <div className={`alert-actions${compact ? " compact" : ""}`}>
      {dismissed ? (
        <>
          <span className="badge">Dismissed</span>
          <Button variant="ghost" size="sm" disabled={review.isPending} onClick={() => review.mutate({ action: "reopened" })}>
            Reopen
          </Button>
        </>
      ) : (
        <>
          <Button
            variant="secondary"
            size="sm"
            disabled={review.isPending || state.reviewed}
            onClick={() => review.mutate({ action: "reviewed" })}
          >
            {state.reviewed ? "Reviewed" : "Mark reviewed"}
          </Button>
          <Button variant="secondary" size="sm" disabled={review.isPending} onClick={() => setNoting(!noting)}>
            Dismiss…
          </Button>
        </>
      )}
      <span className="feedback" role="group" aria-label="Was this alert useful?">
        <span>Useful?</span>
        <button
          className={`icon-button${state.feedback === "useful" ? " pressed" : ""}`}
          aria-pressed={state.feedback === "useful"}
          aria-label="Yes, useful"
          onClick={() => review.mutate({ action: "feedback", feedback: "useful" })}
        >
          <ThumbsUp size={16} />
        </button>
        <button
          className={`icon-button${state.feedback === "not_useful" ? " pressed" : ""}`}
          aria-pressed={state.feedback === "not_useful"}
          aria-label="No, not useful"
          onClick={() => review.mutate({ action: "feedback", feedback: "not_useful" })}
        >
          <ThumbsDown size={16} />
        </button>
      </span>
      {noting && (
        <form
          className="dismiss-form"
          onSubmit={(e) => {
            e.preventDefault();
            review.mutate({ action: "dismissed", note });
          }}
        >
          <label>
            Why dismiss it? (optional, kept with the alert)
            <textarea value={note} rows={2} maxLength={2000} onChange={(e) => setNote(e.target.value)} />
          </label>
          <p className="small muted">It stays hidden unless it gets more serious.</p>
          <Button size="sm" type="submit" disabled={review.isPending}>
            Dismiss alert
          </Button>
        </form>
      )}
      {review.error && (
        <p className="notice error" role="alert">
          {(review.error as Error).message}
        </p>
      )}
    </div>
  );
}

/** "Evidence and actions" drawer: what the data shows in plain English, the source, and the review. */
export function AlertEvidence({
  alert,
  applyToGroup = false,
  properties,
}: {
  alert: AlertLike;
  applyToGroup?: boolean;
  /** Every property a shared alert applies to. */
  properties?: string[];
}) {
  const link = alert.evidence?.source_link as string | undefined;
  const rows = evidenceRows(alert.rule_id, alert.evidence ?? {});
  const terms = SOURCE_TERMS[alert.source ?? ""] ?? [];
  return (
    <Drawer
      title={alert.title}
      description={[
        RULE_NAMES[alert.rule_id] ?? "Alert",
        properties?.length ? properties.join(", ") : alert.location?.name,
        alert.detected_at ? `first seen ${dateLabel(alert.detected_at)}` : null,
      ]
        .filter(Boolean)
        .join(" · ")}
      trigger={
        <button type="button" className="text-link-button">
          Evidence and actions
        </button>
      }
    >
      <div className="evidence-body">
        <p>{alert.why}</p>
        {alert.next_step && (
          <p className="next-step">
            <strong>Next step:</strong> {alert.next_step}
          </p>
        )}
        <dl className="facts">
          <dt>Level</dt>
          <dd>{alert.severity === "FYI" ? "For your information" : alert.severity}</dd>
          {alert.period && (
            <>
              <dt>Data period</dt>
              <dd>{alert.period}</dd>
            </>
          )}
          {rows.map(([label, value]) => (
            <div key={label} style={{ display: "contents" }}>
              <dt>{label}</dt>
              <dd>{value}</dd>
            </div>
          ))}
        </dl>
        {terms.length > 0 && (
          <dl className="glossary">
            {terms.map((t) => (
              <div key={t}>
                <dt>{t}</dt>
                <dd>{GLOSSARY[t]}</dd>
              </div>
            ))}
          </dl>
        )}
        {link && (
          <a href={link} target="_blank" rel="noreferrer">
            Open the source
          </a>
        )}
        {applyToGroup && <p className="fine-print">A review here applies to every property listed above.</p>}
        <AlertActions alert={alert} applyToGroup={applyToGroup} />
      </div>
    </Drawer>
  );
}
