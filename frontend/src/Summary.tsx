import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, Gauge } from "lucide-react";
import { api } from "./api";
import { AlertEvidence } from "./AlertDetails";
import type { Location } from "./types";

export type { SummaryMetric } from "./lib/format/metrics";
import type { SummaryMetric } from "./lib/format/metrics";
export { favourable, formatMetric, severityTone } from "./lib/format/metrics";
import { formatMetric, favourable, severityTone } from "./lib/format/metrics";
export interface SummaryItem {
  text: string;
  metric: string;
  source: string | null;
  period: string | null;
}
export interface SignalItem {
  id: string;
  rule_id: string;
  title: string;
  severity: "High" | "Watch" | "FYI";
  why: string;
  detected_at: string;
  source?: string | null;
  period?: string | null;
  evidence?: Record<string, unknown>;
}
export interface Summary {
  portfolio_size: number;
  min_portfolio: number;
  benchmark_ready: boolean;
  metrics: SummaryMetric[];
  strengths: SummaryItem[];
  concerns: SummaryItem[];
  signals: SignalItem[];
  note: string;
}


export default function SummaryPanel({ location }: { location: Location }) {
  const query = useQuery({
    queryKey: ["summary", location.id, location.analysis_version],
    queryFn: () => api<Summary>(`/api/locations/${location.id}/summary/`),
  });
  if (query.error)
    return (
      <p className="notice error" role="alert">
        The comparison summary could not be loaded.
      </p>
    );
  const d = query.data;
  if (!d) return <p className="notice">Loading comparison…</p>;
  const shown = d.metrics.filter((m) => m.value !== null);
  const nothingYet = shown.length === 0 && d.signals.length === 0;
  return (
    <section className="panel summary-panel" aria-labelledby="summary-title">
      <div className="section-heading">
        <div>
          <span className="eyebrow">SUMMARY</span>
          <h2 id="summary-title">How this location compares</h2>
        </div>
        <Gauge size={22} />
      </div>
      {nothingYet && (
        <p className="notice" role="status">
          Not calculated yet. Use "Calculate ring demographics" and "Check area data" below; this summary fills
          in on its own when they finish.
        </p>
      )}
      {!d.benchmark_ready && (
        <p className="notice">
          Portfolio comparison needs at least {d.min_portfolio} other owned properties with data (you have{" "}
          {d.portfolio_size}).
        </p>
      )}
      {d.signals.length > 0 && (
        <ul className="change-list" aria-label="Active signals">
          {d.signals.map((s) => (
            <li key={s.id}>
              <span className={`badge ${severityTone(s.severity)}`}>{s.severity}</span>
              <div>
                <strong>{s.title}</strong>
                <small>{s.why}</small>
                <AlertEvidence alert={{ ...s, location: { id: location.id, name: location.name } }} />
              </div>
            </li>
          ))}
        </ul>
      )}
      <div className="summary-columns">
        <div>
          <h3>
            <CheckCircle2 size={16} /> Strengths
          </h3>
          {d.strengths.length === 0 ? (
            <p className="small muted">No notable strengths by the standard rules.</p>
          ) : (
            <ul className="summary-list">
              {d.strengths.map((s, i) => (
                <li key={`${i}-${s.metric}`}>
                  {s.text}
                  {s.period && <small> · {s.period}</small>}
                </li>
              ))}
            </ul>
          )}
        </div>
        <div>
          <h3>
            <AlertTriangle size={16} /> Concerns
          </h3>
          {d.concerns.length === 0 ? (
            <p className="small muted">No notable concerns by the standard rules.</p>
          ) : (
            <ul className="summary-list concerns">
              {d.concerns.map((s, i) => (
                <li key={`${i}-${s.metric}`}>
                  {s.text}
                  {s.period && <small> · {s.period}</small>}
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
      {d.benchmark_ready && shown.length > 0 && (
        <details className="area-sources">
          <summary>All compared measures ({shown.length})</summary>
          <ul className="bars percentile-bars">
            {shown.map((m) => {
              const f = favourable(m);
              return (
                <li key={m.key}>
                  <span>{m.label}</span>
                  <span className="bar" aria-hidden="true">
                    {f !== null && <span style={{ width: `${Math.max(2, f)}%` }} />}
                  </span>
                  <strong>
                    {formatMetric(m)}
                    <small>{f === null ? "no benchmark" : `better than ${f}%`}</small>
                  </strong>
                </li>
              );
            })}
          </ul>
        </details>
      )}
      <p className="small muted">{d.note}</p>
    </section>
  );
}
