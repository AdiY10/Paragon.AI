import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as Dialog from "@radix-ui/react-dialog";
import { Activity, RefreshCw, X } from "lucide-react";
import { api, dateLabel } from "./api";
import { severityTone } from "./Summary";

export interface BriefItem {
  id: string;
  rule_id: string;
  title: string;
  severity: "High" | "Watch" | "FYI";
  category: string;
  why: string;
  period: string;
  source: string | null;
  evidence: Record<string, unknown>;
  flag: "new" | "changed" | "still_active";
  location: { id: string; name: string; city: string; state: string };
}
export interface Brief {
  id: string;
  kind: "baseline" | "weekly" | "manual";
  title: string;
  generated_at: string;
  since: string | null;
  items: BriefItem[];
  fyi: BriefItem[];
  sources_updated: { id: string; name: string; period: string }[];
  stats: Record<string, number>;
}

export const flagLabel = (f: BriefItem["flag"]) =>
  f === "new" ? "New" : f === "changed" ? "Changed" : "Still active";

export default function ThisWeek({ isAdmin }: { isAdmin: boolean }) {
  const [selected, setSelected] = useState<string | null>(null);
  const cache = useQueryClient();
  const latest = useQuery({
    queryKey: ["brief", "latest"],
    queryFn: () => api<{ brief: Brief | null; history: { id: string; title: string; generated_at: string }[] }>("/api/briefs/latest/"),
  });
  const past = useQuery({
    queryKey: ["brief", selected],
    enabled: !!selected,
    queryFn: () => api<Brief>(`/api/briefs/${selected}/`),
  });
  const generate = useMutation({
    mutationFn: () => api<Brief>("/api/briefs/generate/", "POST"),
    onSuccess: () => {
      setSelected(null);
      cache.invalidateQueries({ queryKey: ["brief"] });
    },
  });
  if (latest.error) return <p className="notice error">The weekly brief could not be loaded.</p>;
  if (!latest.data) return <p className="notice">Loading this week's brief…</p>;
  const brief = selected && past.data ? past.data : latest.data.brief;
  return (
    <section className="panel brief" aria-labelledby="brief-title">
      <div className="section-heading">
        <div>
          <span className="eyebrow">THIS WEEK</span>
          <h2 id="brief-title">{brief ? brief.title : "No brief generated yet"}</h2>
        </div>
        <Activity size={22} />
      </div>
      {!brief ? (
        <p className="muted">
          The first brief is generated on Monday at 7:00 a.m. Eastern{isAdmin ? ", or generate one now." : "."} It will
          list current conditions as a baseline.
        </p>
      ) : (
        <>
          <p className="trade-meta">
            <span>
              {dateLabel(brief.generated_at)}
              {brief.since ? ` · changes since ${dateLabel(brief.since)}` : " · baseline of current conditions"}
            </span>
          </p>
          {brief.items.length === 0 ? (
            <p className="notice">No material changes across your properties since the last brief.</p>
          ) : (
            <ul className="change-list brief-items">
              {brief.items.map((i) => (
                <BriefRow key={i.id} item={i} />
              ))}
            </ul>
          )}
          {brief.fyi.length > 0 && (
            <details className="area-sources">
              <summary>
                {brief.fyi.length} other update{brief.fyi.length === 1 ? "" : "s"} (FYI)
              </summary>
              <ul className="change-list">
                {brief.fyi.map((i) => (
                  <BriefRow key={i.id} item={i} />
                ))}
              </ul>
            </details>
          )}
          {brief.sources_updated.length > 0 && (
            <details className="area-sources">
              <summary>Sources updated ({brief.sources_updated.length})</summary>
              <ul className="evidence-list">
                {brief.sources_updated.map((s) => (
                  <li key={s.id}>
                    {s.name}: {s.period}
                  </li>
                ))}
              </ul>
            </details>
          )}
        </>
      )}
      <div className="brief-actions">
        {latest.data.history.length > 1 && (
          <label>
            Past briefs{" "}
            <select value={selected ?? ""} onChange={(e) => setSelected(e.target.value || null)}>
              <option value="">Latest</option>
              {latest.data.history.slice(1).map((h) => (
                <option key={h.id} value={h.id}>
                  {dateLabel(h.generated_at)} · {h.title}
                </option>
              ))}
            </select>
          </label>
        )}
        {isAdmin && (
          <button className="button secondary small-button" disabled={generate.isPending} onClick={() => generate.mutate()}>
            <RefreshCw size={14} /> {generate.isPending ? "Generating…" : "Generate brief now"}
          </button>
        )}
      </div>
    </section>
  );
}

function BriefRow({ item }: { item: BriefItem }) {
  return (
    <li>
      <span className={`badge ${severityTone(item.severity)}`}>{item.severity}</span>
      <div>
        <strong>
          <a href={`#/locations/${item.location.id}`}>{item.location.name}</a>: {item.title}
        </strong>
        <small>
          {item.location.city}, {item.location.state} · {flagLabel(item.flag)} · {item.period}
        </small>
        <small>{item.why}</small>
        <Evidence item={item} />
      </div>
    </li>
  );
}

function Evidence({ item }: { item: BriefItem }) {
  const link = item.evidence.source_link as string | undefined;
  return (
    <Dialog.Root>
      <Dialog.Trigger asChild>
        <button className="text-button small">Evidence</button>
      </Dialog.Trigger>
      <Dialog.Portal>
        <Dialog.Overlay className="overlay" />
        <Dialog.Content className="drawer">
          <div className="drawer-head">
            <Dialog.Title>{item.title}</Dialog.Title>
            <Dialog.Close className="icon-button" aria-label="Close evidence">
              <X />
            </Dialog.Close>
          </div>
          <Dialog.Description className="muted">
            Rule {item.rule_id} · {item.location.name}
          </Dialog.Description>
          <p>{item.why}</p>
          <dl className="facts">
            <dt>Severity</dt>
            <dd>{item.severity}</dd>
            <dt>Data period</dt>
            <dd>{item.period}</dd>
            {Object.entries(item.evidence)
              .filter(([k, v]) => k !== "source_link" && v !== null && typeof v !== "object")
              .map(([k, v]) => (
                <div key={k} style={{ display: "contents" }}>
                  <dt>{k.replaceAll("_", " ")}</dt>
                  <dd>{String(v)}</dd>
                </div>
              ))}
          </dl>
          {link && (
            <a className="text-button" href={link} target="_blank" rel="noreferrer">
              Open the source
            </a>
          )}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
