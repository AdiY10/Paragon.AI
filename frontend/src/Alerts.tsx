import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, dateLabel } from "./api";
import { AlertEvidence, type AlertLike } from "./AlertDetails";
import { RULE_NAMES } from "./alertText";
import { severityTone } from "./Summary";

type Alert = AlertLike & { category: string; status: string; changed_at: string; location: { id: string; name: string; city: string; state: string } };

/** Every alert across the portfolio, filterable (R2 item 20). */
export default function AlertsPage() {
  const params = new URLSearchParams(window.location.hash.split("?")[1] ?? "");
  const [status, setStatus] = useState(params.get("status") ?? "active");
  const [severity, setSeverity] = useState(params.get("severity") ?? "");
  const [category, setCategory] = useState(params.get("category") ?? "");
  const [property, setProperty] = useState(params.get("property") ?? "");
  const q = useQuery({
    queryKey: ["signals", status],
    queryFn: () => api<{ results: Alert[] }>(`/api/signals/?status=${status}`),
  });
  const all = q.data?.results ?? [];
  const shown = all.filter(
    (a) =>
      (!severity || a.severity === severity) &&
      (!category || a.category === category) &&
      (!property || a.location.id === property),
  );
  const properties = [...new Map(all.map((a) => [a.location.id, a.location.name])).entries()].sort((a, b) =>
    a[1].localeCompare(b[1]),
  );
  const categories = [...new Set(all.map((a) => a.category))].sort();
  return (
    <>
      <header className="page-head">
        <div>
          <span className="eyebrow">ALERTS</span>
          <h1>All alerts</h1>
          <p>Every alert across your properties. Open one to see the evidence, review it or dismiss it.</p>
        </div>
      </header>
      <div className="filterbar">
        <span>{shown.length} alerts</span>
        <label>
          Status
          <select value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="active">Active</option>
            <option value="dismissed">Dismissed</option>
            <option value="resolved">Resolved</option>
            <option value="expired">Expired</option>
            <option value="all">All</option>
          </select>
        </label>
        <label>
          Level
          <select value={severity} onChange={(e) => setSeverity(e.target.value)}>
            <option value="">Any level</option>
            <option value="High">High</option>
            <option value="Watch">Watch</option>
            <option value="FYI">FYI</option>
          </select>
        </label>
        <label>
          Category
          <select value={category} onChange={(e) => setCategory(e.target.value)}>
            <option value="">Any category</option>
            {categories.map((c) => (
              <option key={c}>{c}</option>
            ))}
          </select>
        </label>
        <label>
          Property
          <select value={property} onChange={(e) => setProperty(e.target.value)}>
            <option value="">All properties</option>
            {properties.map(([id, name]) => (
              <option key={id} value={id}>
                {name}
              </option>
            ))}
          </select>
        </label>
      </div>
      <section className="panel">
        {q.error ? (
          <p className="notice error" role="alert">
            Alerts could not be loaded.
          </p>
        ) : !q.data ? (
          <p className="notice">Loading alerts…</p>
        ) : shown.length === 0 ? (
          <p className="notice">No alerts match these filters.</p>
        ) : (
          <ul className="change-list alert-list">
            {shown.map((a) => (
              <li key={a.id}>
                <span className={`badge ${severityTone(a.severity)}`}>{a.severity}</span>
                <div>
                  <strong>
                    <a href={`#/p/${a.location.id}`}>{a.location.name}</a>: {a.title}
                  </strong>
                  <small>
                    {RULE_NAMES[a.rule_id] ?? a.category} · {a.location.city}, {a.location.state} · since{" "}
                    {dateLabel(a.detected_at ?? a.changed_at)}
                    {a.status !== "active" && ` · ${a.status}`}
                    {a.reviewed && a.status === "active" && " · reviewed"}
                  </small>
                  <AlertEvidence alert={a} />
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>
    </>
  );
}
