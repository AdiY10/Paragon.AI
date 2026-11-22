import { useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, Layers3, Plus, Search, X } from "lucide-react";
import { api, allLocations, dateLabel } from "./api";
import type { Location } from "./types";
import { formatMetric } from "./Summary";
import { takePendingAddress } from "./app/nav";

// ---- compare selection (per-viewer convenience; never required for correctness) ----
const KEY = "paragon.compare";
export function readCompare(): string[] {
  try {
    const v = JSON.parse(localStorage.getItem(KEY) ?? "[]");
    return Array.isArray(v) ? v.filter((x) => typeof x === "string").slice(0, 4) : [];
  } catch {
    return [];
  }
}
export function writeCompare(ids: string[]) {
  try {
    localStorage.setItem(KEY, JSON.stringify(ids.slice(0, 4)));
  } catch {
    /* storage unavailable: selection lasts for this page only */
  }
}
export function toggleCompare(ids: string[], id: string): string[] {
  return ids.includes(id) ? ids.filter((x) => x !== id) : [...ids, id].slice(-4);
}

export function CompareButton({ id }: { id: string }) {
  const [ids, setIds] = useState(readCompare());
  const on = ids.includes(id);
  return (
    <button
      className="button secondary small-button"
      onClick={() => {
        const next = toggleCompare(ids, id);
        writeCompare(next);
        setIds(next);
      }}
    >
      <Layers3 size={14} /> {on ? "Remove from compare" : "Add to compare"} ({(on ? ids.length : Math.min(4, ids.length + 1))}/4)
    </button>
  );
}

// ---- Screen (FR-25) ----
interface ScreenResponse {
  location: Location;
  geocode_status: string;
  jobs: string[];
}

export function ScreenPage() {
  const [initialAddress] = useState(takePendingAddress);
  const cache = useQueryClient();
  const [message, setMessage] = useState("");
  const recent = useQuery({ queryKey: ["screens"], queryFn: () => api<{ results: Location[] }>("/api/screens/") });
  const screen = useMutation({
    mutationFn: (body: { address: string; name: string }) => api<ScreenResponse>("/api/screens/", "POST", body),
    onSuccess: (r) => {
      cache.invalidateQueries({ queryKey: ["screens"] });
      if (r.geocode_status !== "matched")
        setMessage("The address needs a pin. Use 'Find address pin' or 'Correct / confirm pin' on the next page.");
      window.location.hash = `#/analyze/${r.location.id}`;
    },
  });
  function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const data = new FormData(e.currentTarget);
    screen.mutate({ address: String(data.get("address") ?? ""), name: String(data.get("name") ?? "") });
  }
  return (
    <>
      <header className="page-head">
        <div>
          <span className="eyebrow">Acquisitions</span>
          <h1>Screen a location.</h1>
          <p>
            Enter any US address for a first-pass read: trade area, jobs, economy, traffic, hazards and nearby
            businesses, compared with your portfolio.
          </p>
        </div>
      </header>
      <section className="panel">
        <form className="screen-form" onSubmit={submit}>
          <label>
            Address
            <input name="address" required maxLength={500} defaultValue={initialAddress} placeholder="e.g. 1200 Ulster Avenue, Kingston, NY" />
          </label>
          <label>
            Name (optional)
            <input name="name" maxLength={200} placeholder="e.g. Broker package: Route 9W center" />
          </label>
          <button className="button" disabled={screen.isPending}>
            <Search size={16} /> {screen.isPending ? "Screening…" : "Screen this address"}
          </button>
        </form>
        {screen.error && (
          <p className="notice error" role="alert">
            {(screen.error as Error).message}
          </p>
        )}
        {message && <p className="notice">{message}</p>}
        <p className="small muted">
          Screens are private and not monitored until you save them as a candidate. Unsaved screens are archived after
          30 days. The address is sent to the U.S. Census geocoder only.
        </p>
      </section>
      <section className="panel">
        <h2>Recent screens</h2>
        {!recent.data ? (
          <p className="notice">Loading…</p>
        ) : recent.data.results.length === 0 ? (
          <p className="muted">No screens yet.</p>
        ) : (
          <ul className="anchor-list">
            {recent.data.results.map((l) => (
              <li key={l.id}>
                <a href={`#/analyze/${l.id}`}>{l.name}</a>
                <small>{dateLabel(l.created_at)}</small>
              </li>
            ))}
          </ul>
        )}
      </section>
    </>
  );
}

export function ScreenBanner({ location }: { location: Location }) {
  const cache = useQueryClient();
  const save = useMutation({
    mutationFn: () => api<Location>(`/api/screens/${location.id}/save/`, "POST"),
    onSuccess: () => {
      cache.invalidateQueries({ queryKey: ["location", location.id] });
      cache.invalidateQueries({ queryKey: ["locations"] });
      cache.invalidateQueries({ queryKey: ["screens"] });
    },
  });
  if (!location.screening) return null;
  return (
    <div className="notice screen-banner" role="status">
      <span>
        <strong>Unsaved screen.</strong> Not monitored and not in your weekly brief. Save it to track this location.
      </span>
      <button className="button small-button" disabled={save.isPending} onClick={() => save.mutate()}>
        <Plus size={14} /> Save as candidate
      </button>
    </div>
  );
}

// ---- Compare (FR-27) ----
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
  const [ids, setIds] = useState(readCompare());
  const all = useQuery({ queryKey: ["locations", "all-for-compare"], queryFn: allLocations });
  const data = useQuery({
    queryKey: ["compare", ids.join(",")],
    enabled: ids.length >= 2,
    queryFn: () => api<CompareData>(`/api/compare/?ids=${ids.join(",")}`),
  });
  const update = (next: string[]) => {
    writeCompare(next);
    setIds(next);
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
