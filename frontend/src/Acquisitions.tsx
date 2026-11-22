import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, X } from "lucide-react";
import { api, allLocations } from "./api";
import type { Location } from "./types";
import { formatMetric } from "./lib/format/metrics";
import { navigate, parseHash } from "./app/router";
import { parseIds, readSelection, writeSelection } from "./features/compare/selection";

// ---- Compare (restyled in WI-8) ----
interface CompareRow {
  key: string;
  label: string;
  unit: string;
  direction: "up" | "down";
  group: string;
  cells: Record<string, { value: number | null; period: string | null; source: string | null; detail: string | null; best: boolean; worst: boolean }>;
  portfolio: { median: number; min: number; max: number; n: number } | null;
}
interface CompareData {
  locations: {
    id: string;
    name: string;
    city: string;
    state: string;
    status: string;
    screening: boolean;
    attention: string;
    flood_zone: string | null;
    sfha: boolean;
    nri_rating: string | null;
    signals: { title: string; severity: string }[];
  }[];
  rows: CompareRow[];
  note: string;
}

export function ComparePage() {
  // ?ids= wins (links from the Properties tray); otherwise the stored selection.
  const [ids, setIds] = useState(() => {
    const fromUrl = parseIds(parseHash(window.location.hash).query.get("ids"));
    return fromUrl.length ? fromUrl : readSelection();
  });
  const all = useQuery({ queryKey: ["locations", "all-for-compare"], queryFn: allLocations });
  const data = useQuery({
    queryKey: ["compare", ids.join(",")],
    enabled: ids.length >= 2,
    queryFn: () => api<CompareData>(`/api/compare/?ids=${ids.join(",")}`),
  });
  const update = (next: string[]) => {
    writeSelection(next);
    setIds(next);
    navigate(next.length ? "/compare?ids=" + next.join(",") : "/compare", { replace: true });
  };
  const options = (all.data ?? []).filter((l) => l.status !== "archived" && !ids.includes(l.id) && l.current_revision.lat !== null);
  const groups = [...new Set((data.data?.rows ?? []).map((r) => r.group))];
  return (
    <>
      <header className="page-head">
        <div>
          <span className="eyebrow">Acquisitions</span>
          <h1>Compare locations.</h1>
          <p>Up to four locations side by side, with your portfolio's median and range.</p>
        </div>
      </header>
      <section className="panel">
        <div className="compare-picker">
          {ids.map((id) => {
            const l = (all.data ?? []).find((x) => x.id === id);
            return (
              <span className="chip" key={id}>
                {l?.name ?? "Location"}
                <button aria-label={`Remove ${l?.name ?? "location"}`} onClick={() => update(ids.filter((x) => x !== id))}>
                  <X size={12} />
                </button>
              </span>
            );
          })}
          {ids.length < 4 && (
            <label>
              <span className="sr-only">Add a location</span>
              <select value="" onChange={(e) => e.target.value && update([...ids, e.target.value])}>
                <option value="">+ Add a location…</option>
                {options.map((l) => (
                  <option key={l.id} value={l.id}>
                    {l.name} ({l.city ? `${l.city}, ` : ""}
                    {l.state}){l.screening ? " · screen" : l.status === "candidate" ? " · candidate" : ""}
                  </option>
                ))}
              </select>
            </label>
          )}
        </div>
        {ids.length < 2 && <p className="muted">Choose at least two locations. You can also use "Add to compare" on any property page.</p>}
      </section>
      {data.error && <p className="notice error">The comparison could not be loaded.</p>}
      {data.data && (
        <section className="panel">
          <div className="table-wrap">
            <table className="ring-table compare-table">
              <thead>
                <tr>
                  <th scope="col">Measure</th>
                  {data.data.locations.map((l) => (
                    <th scope="col" key={l.id}>
                      <a href={`#/p/${l.id}`}>{l.name}</a>
                      <small>
                        {l.city}, {l.state}
                        {l.attention !== "Clear" ? ` · ${l.attention}` : ""}
                      </small>
                    </th>
                  ))}
                  <th scope="col">Portfolio median (range)</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <th scope="row">Flood zone at pin</th>
                  {data.data.locations.map((l) => (
                    <td key={l.id} className={l.sfha ? "worst" : ""}>
                      <strong>{l.flood_zone ?? "Unavailable"}</strong>
                      {l.sfha && <small>Special Flood Hazard Area</small>}
                    </td>
                  ))}
                  <td>
                    <small>Not compared</small>
                  </td>
                </tr>
              </tbody>
              {groups.map((g) => (
                <tbody key={g}>
                  <tr>
                    <th scope="colgroup" colSpan={data.data.locations.length + 2} className="group-row">
                      {g}
                    </th>
                  </tr>
                  {data.data.rows
                    .filter((r) => r.group === g)
                    .map((r) => (
                      <tr key={r.key}>
                        <th scope="row">{r.label}</th>
                        {data.data.locations.map((l) => {
                          const c = r.cells[l.id];
                          return (
                            <td key={l.id} className={c.best ? "best" : c.worst ? "worst" : ""}>
                              <strong>{formatMetric({ unit: r.unit, value: c.value })}</strong>
                              {c.period && <small>{c.period}</small>}
                              {c.best && <span className="sr-only"> (strongest)</span>}
                              {c.worst && <span className="sr-only"> (weakest)</span>}
                            </td>
                          );
                        })}
                        <td>
                          {r.portfolio ? (
                            <>
                              <strong>{formatMetric({ unit: r.unit, value: r.portfolio.median })}</strong>
                              <small>
                                {formatMetric({ unit: r.unit, value: r.portfolio.min })} to{" "}
                                {formatMetric({ unit: r.unit, value: r.portfolio.max })} · n={r.portfolio.n}
                              </small>
                            </>
                          ) : (
                            <small>No portfolio data</small>
                          )}
                        </td>
                      </tr>
                    ))}
                </tbody>
              ))}
            </table>
          </div>
          <p className="small muted">{data.data.note}</p>
          <button className="button secondary small-button" onClick={() => window.print()}>
            Print or save as PDF <ArrowRight size={14} />
          </button>
        </section>
      )}
    </>
  );
}
