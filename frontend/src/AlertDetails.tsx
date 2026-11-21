import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import * as Dialog from "@radix-ui/react-dialog";
import { ThumbsDown, ThumbsUp, X } from "lucide-react";
import { api, dateLabel } from "./api";
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
export function AlertActions({ alert, compact = false }: { alert: AlertLike; compact?: boolean }) {
  const cache = useQueryClient();
  const [note, setNote] = useState(alert.review_note ?? "");
  const [noting, setNoting] = useState(false);
  const [state, setState] = useState({ status: alert.status, reviewed: alert.reviewed, feedback: alert.feedback });
  const review = useMutation({
    mutationFn: (body: Record<string, string>) => api<AlertLike>(`/api/signals/${alert.id}/review/`, "POST", body),
    onSuccess: (s) => {
      setState({ status: s.status, reviewed: s.reviewed, feedback: s.feedback });
      setNoting(false);
      for (const key of ["signals", "summary", "locations", "location"]) cache.invalidateQueries({ queryKey: [key] });
    },
  });
  const dismissed = state.status === "dismissed";
  return (
    <div className={`alert-actions${compact ? " compact" : ""}`}>
      {dismissed ? (
        <>
          <span className="badge">Dismissed</span>
          <button className="text-button" disabled={review.isPending} onClick={() => review.mutate({ action: "reopened" })}>
            Reopen
          </button>
        </>
      ) : (
        <>
          <button
            className="button secondary small-button"
            disabled={review.isPending || state.reviewed}
            onClick={() => review.mutate({ action: "reviewed" })}
          >
            {state.reviewed ? "Reviewed" : "Mark reviewed"}
          </button>
          <button className="button secondary small-button" disabled={review.isPending} onClick={() => setNoting(!noting)}>
            Dismiss…
          </button>
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
          <button className="button small-button" type="submit" disabled={review.isPending}>
            Dismiss alert
          </button>
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

/** "Evidence" button and drawer: what the data shows in plain English, the source, and actions. */
export function AlertEvidence({ alert }: { alert: AlertLike }) {
  const link = alert.evidence?.source_link as string | undefined;
  const rows = evidenceRows(alert.rule_id, alert.evidence ?? {});
  const terms = SOURCE_TERMS[alert.source ?? ""] ?? [];
  return (
    <Dialog.Root>
      <Dialog.Trigger asChild>
        <button className="text-button small">Evidence and actions</button>
      </Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Overlay className="overlay" />
        <Dialog.Content className="drawer">
          <div className="drawer-head">
            <Dialog.Title>{alert.title}</Dialog.Title>
            <Dialog.Close className="icon-button" aria-label="Close evidence">
              <X />
            </Dialog.Close>
          </div>
          <Dialog.Description className="muted">
            {RULE_NAMES[alert.rule_id] ?? "Alert"}
            {alert.location ? ` · ${alert.location.name}` : ""}
            {alert.detected_at ? ` · first seen ${dateLabel(alert.detected_at)}` : ""}
          </Dialog.Description>
          <p>{alert.why}</p>
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
            <a className="text-button" href={link} target="_blank" rel="noreferrer">
              Open the source
            </a>
          )}
          <AlertActions alert={alert} />
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
