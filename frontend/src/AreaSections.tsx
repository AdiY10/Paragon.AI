import { useEffect, useState, type ReactNode } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Briefcase, Building, Car, RefreshCw, ShieldAlert, Store } from "lucide-react";
import { api, dateLabel } from "./api";
import type { Location } from "./types";
import { reasonText } from "./demographics";
import {
  count,
  floodHeadline,
  floodTone,
  sfhaDistance,
  money,
  monthLabel,
  pct,
  signedPct,
  signedPts,
  miles,
  placeName,
  releaseLabel,
  type Area,
  type Businesses,
  type Economy,
  type Hazards,
  type Jobs,
  type Section,
  type SourceRef,
  type Traffic,
} from "./area";

const POLL_MS = 4000;
const POLL_LIMIT_MS = 240_000;

export default function AreaSections({ location, autoStart = false }: { location: Location; autoStart?: boolean }) {
  const [pollingSince, setPollingSince] = useState<number | null>(null);
  const query = useQuery({
    queryKey: ["area", location.id, location.analysis_version],
    queryFn: () => api<Area>(`/api/locations/${location.id}/area/`),
    refetchInterval: (q) => {
      const s = q.state.data?.sections;
      const pending = !s || Object.values(s).some((x) => x.status === "not_computed");
      return pollingSince !== null && pending ? POLL_MS : false;
    },
  });
  const compute = useMutation({
    mutationFn: () =>
      api(`/api/locations/${location.id}/area/`, "POST"),
    onSuccess: () => setPollingSince(Date.now()),
  });
  const sections = query.data?.sections;
  const allDone =
    !!sections && Object.values(sections).every((s) => s.status !== "not_computed");
  const timedOut =
    pollingSince !== null && !allDone && Date.now() - pollingSince > POLL_LIMIT_MS;
  useEffect(() => {
    if (allDone || timedOut) setPollingSince(null);
  }, [allDone, timedOut]);

  const missing = !!sections && Object.values(sections).some((s) => s.status === "not_computed" && s.reason === "NOT_COMPUTED");
  useEffect(() => {
    if (autoStart && query.data?.placed && missing && pollingSince === null && !compute.isPending) compute.mutate();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoStart, missing, query.data?.placed]);
  if (query.error)
    return (
      <p className="notice error" role="alert">
        Area data could not be loaded. Please try again.
      </p>
    );
  if (!sections) return <p className="notice">Loading area data…</p>;

  const computing = pollingSince !== null || compute.isPending;
  const anyMissing = Object.values(sections).some((s) => s.status === "not_computed");
  const stale = Object.values(sections).some((s) => s.reason === "STALE");
  const action = query.data!.placed && anyMissing && (
    <div className="area-action">
      <p>
        {computing
          ? "Checking federal sources… this usually takes under a minute."
          : stale
            ? "The pin moved. Re-check area data for the new location."
            : "Economy, traffic, hazards and nearby businesses have not been checked for this location yet."}
      </p>
      {timedOut && (
        <p className="notice error" role="alert">
          The check has not finished. The background worker may be busy or stopped.
        </p>
      )}
      {compute.error && (
        <p className="notice error" role="alert">
          {(compute.error as Error).message}
        </p>
      )}
      {!computing && (
        <button className="button small-button" onClick={() => compute.mutate()}>
          <RefreshCw size={15} /> Check area data
        </button>
      )}
    </div>
  );

  return (
    <>
      {action && <section className="panel">{action}</section>}
      {/* FR-08 order: economy and jobs, retail landscape, access and traffic, hazards */}
      <div id="economy" className="page-section" tabIndex={-1}>
        <EconomyPanel section={sections.economy} />
        <JobsPanel section={sections.jobs} />
      </div>
      <div id="retail" className="page-section" tabIndex={-1}>
        <BusinessesPanel section={sections.businesses} />
      </div>
      <div className="location-columns">
        <div id="traffic" className="page-section" tabIndex={-1}>
          <TrafficPanel section={sections.traffic} />
        </div>
        <div id="hazards" className="page-section" tabIndex={-1}>
          <HazardsPanel section={sections.hazards} />
        </div>
      </div>
    </>
  );
}

function Panel({
  eyebrow,
  title,
  icon,
  section,
  children,
}: {
  eyebrow: string;
  title: string;
  icon: ReactNode;
  section: Section<unknown>;
  children: ReactNode;
}) {
  return (
    <section className="panel area-panel">
      <div className="section-heading">
        <div>
          <span className="eyebrow">{eyebrow}</span>
          <h2>{title}</h2>
        </div>
        {icon}
      </div>
      {section.stale && (
        <p className="notice" role="status">
          Stale: a source could not be refreshed, so the last good values are shown with their dates.
        </p>
      )}
      {section.status === "not_computed" ? (
        <p className="muted">
          {section.reason === "STALE" ? "Out of date for the current pin." : "Not checked yet."}
        </p>
      ) : section.status === "unavailable" &&
        (!section.data || Object.keys(section.data).length <= 1) ? (
        <p className="muted">{reasonText(section.data?.reason)}</p>
      ) : (
        children
      )}
      {section.sources && section.sources.length > 0 && (
        <Sources sources={section.sources} computedAt={section.computed_at} />
      )}
    </section>
  );
}

function Sources({ sources, computedAt }: { sources: SourceRef[]; computedAt?: string }) {
  return (
    <details className="area-sources">
      <summary>
        Sources · checked {dateLabel(computedAt)}
      </summary>
      <ul className="evidence-list">
        {sources.map((s) => (
          <li key={s.id + s.period}>
            <a href={s.url} target="_blank" rel="noreferrer">
              {s.name}
            </a>{" "}
            · {monthLabel(s.period)} · checked {dateLabel(s.checked_at ?? s.retrieved_at)}
            {s.stale && <span className="badge amber"> Stale</span>}
          </li>
        ))}
      </ul>
    </details>
  );
}

function Stat({
  label,
  value,
  detail,
  note,
}: {
  label: string;
  value: string;
  detail?: string;
  note?: string;
}) {
  return (
    <div className="area-stat">
      <span>{label}</span>
      <strong>{value}</strong>
      {detail && <small>{detail}</small>}
      {note && <small className="muted">{note}</small>}
    </div>
  );
}

function EconomyPanel({ section }: { section: Section<Economy> }) {
  const d = section.data;
  return (
    <Panel
      eyebrow="LOCAL ECONOMY"
      title={d?.county ? `Jobs and housing in ${d.county.name}` : "Local economy"}
      icon={<Briefcase size={22} />}
      section={section}
    >
      {d && (
        <>
          <p className="trade-meta">
            <span className="badge">Reported</span>
            <span>County-level figures: they describe the local economy, not this property.</span>
          </p>
          <div className="area-stats">
            <Stat
              label="Private-sector jobs"
              value={count(d.employment.private?.value)}
              detail={
                d.employment.private?.value != null
                  ? d.employment.private.yoy_pct != null
                    ? `${signedPct(d.employment.private.yoy_pct)} vs a year earlier`
                    : `Change vs a year earlier: ${reasonText(d.employment.private.yoy_reason).toLowerCase()}`
                  : reasonText(d.employment.private?.reason ?? d.employment.reason)
              }
              note={d.employment.period}
            />
            <Stat
              label="Retail jobs"
              value={count(d.employment.retail?.value)}
              detail={
                d.employment.retail?.value != null
                  ? d.employment.retail.yoy_pct != null
                    ? `${signedPct(d.employment.retail.yoy_pct)} vs a year earlier`
                    : `Change vs a year earlier: ${reasonText(d.employment.retail.yoy_reason).toLowerCase()}`
                  : reasonText(d.employment.retail?.reason ?? d.employment.reason)
              }
              note={
                d.employment.retail?.avg_weekly_wage
                  ? `Avg weekly wage ${money(d.employment.retail.avg_weekly_wage)}`
                  : undefined
              }
            />
            <Stat
              label="Unemployment rate"
              value={d.unemployment.rate != null ? pct(d.unemployment.rate) : reasonText(d.unemployment.reason)}
              detail={
                d.unemployment.rate != null
                  ? `${signedPts(d.unemployment.change_pts)} vs a year earlier`
                  : undefined
              }
              note={
                d.unemployment.period
                  ? `${monthLabel(d.unemployment.period)}${d.unemployment.preliminary ? " (preliminary)" : ""} · not seasonally adjusted`
                  : undefined
              }
            />
            <Stat
              label="New homes permitted"
              value={count(d.permits.value)}
              detail={
                d.permits.value != null
                  ? `${signedPct(d.permits.change_pct)} vs prior 12 months (${count(d.permits.prior)})`
                  : reasonText(d.permits.reason)
              }
              note={monthLabel(d.permits.period)}
            />
          </div>
        </>
      )}
    </Panel>
  );
}

function TrafficPanel({ section }: { section: Section<Traffic> }) {
  const d = section.data;
  return (
    <Panel eyebrow="ACCESS" title="Traffic past the site" icon={<Car size={22} />} section={section}>
      {d && d.roads.length === 0 && (
        <p className="muted">No federal traffic count within {d.radius_m} m of this pin.</p>
      )}
      {d && d.roads.length > 0 && (
        <>
          <ul className="road-list">
            {d.roads.map((r) => (
              <li key={r.label}>
                <div>
                  <strong>{r.label}</strong>
                  <small>
                    {[
                      r.road_class,
                      r.lanes ? `${r.lanes} lanes` : null,
                      r.distance_m != null ? `about ${r.distance_m} m from the pin` : null,
                    ]
                      .filter(Boolean)
                      .join(" · ")}
                  </small>
                </div>
                <div className="road-count">
                  <strong>{count(r.aadt)}</strong>
                  <small>
                    vehicles/day · {r.year}
                    {r.count_year && r.count_year !== r.year ? ` (counted ${r.count_year})` : ""}
                  </small>
                  <small>
                    {r.change_pct != null
                      ? `${signedPct(r.change_pct)} vs ${r.prior_year}`
                      : r.reason === "SAME_COUNT"
                        ? "Estimate carried forward; no new count"
                        : "No prior-year comparison"}
                  </small>
                </div>
              </li>
            ))}
          </ul>
          <p className="small muted">{d.note}</p>
        </>
      )}
    </Panel>
  );
}

function HazardsPanel({ section }: { section: Section<Hazards> }) {
  const d = section.data;
  return (
    <Panel eyebrow="RISK" title="Flood and natural hazards" icon={<ShieldAlert size={22} />} section={section}>
      {d && (
        <>
          {d.concerns.length > 0 && (
            <ul className="concern-list" aria-label="Concerns">
              {d.concerns.map((c) => (
                <li key={c}>{c}</li>
              ))}
            </ul>
          )}
          <dl className="facts">
            <dt>FEMA flood zone at pin</dt>
            <dd>
              <span className={`badge ${floodTone(d.flood_at_pin)}`}>{floodHeadline(d.flood_at_pin)}</span>
              {d.flood_at_pin.bfe_ft != null && <small> Base flood elevation {d.flood_at_pin.bfe_ft} ft</small>}
            </dd>
            <dt>Nearest high-risk flood zone</dt>
            <dd>
              {sfhaDistance(d.flood_nearby) ?? (d.flood_nearby.reason ? reasonText(d.flood_nearby.reason) : "None within 150 m")}
              {d.flood_nearby.sfha && d.flood_nearby.zone && <small> · zone {d.flood_nearby.zone}</small>}
            </dd>
            <dt>National Risk Index (tract)</dt>
            <dd>
              {d.nri.rating ?? reasonText(d.nri.reason)}
              {d.nri.percentile != null && <small> · {d.nri.percentile} percentile nationally</small>}
            </dd>
            {d.nri.top_hazards && d.nri.top_hazards.length > 0 && (
              <>
                <dt>Highest-rated hazards</dt>
                <dd>{d.nri.top_hazards.map((h) => `${h.hazard} (${h.rating})`).join(", ")}</dd>
              </>
            )}
          </dl>
          <p className="small muted">{d.disclaimer} NRI ratings are modelled and relative.</p>
        </>
      )}
    </Panel>
  );
}

function BusinessesPanel({ section }: { section: Section<Businesses> }) {
  const d = section.data;
  return (
    <Panel eyebrow="RETAIL LANDSCAPE" title="Nearby businesses" icon={<Store size={22} />} section={section}>
      {d && d.counts && (
        <>
          <p className="trade-meta">
            <span className="badge">Map data</span>
            <span>
              Overture Maps, {releaseLabel(d.release)} release. Listings may be incomplete; changes are
              possible, not confirmed.
            </span>
          </p>
          <div className="area-stats three">
            <Stat
              label="Retail and service businesses"
              value={count(d.retail_and_services_total["1mi"])}
              detail="within 1 mile"
              note={`${count(d.retail_and_services_total["3mi"])} within 3 miles`}
            />
            <Stat
              label="Nearest supermarket chain"
              value={d.nearest_supermarket ? miles(d.nearest_supermarket.distance_mi) : "None within 3 mi"}
              detail={d.nearest_supermarket ? placeName(d.nearest_supermarket) : "From a list of known chains"}
            />
            <Stat
              label="Marked closed within 1 mile"
              value={count(d.closed_within_1mi)}
              detail="Places Overture lists as permanently closed"
            />
          </div>
          <Changes d={d} />
          <div className="business-columns">
            <div>
              <h3>Mix within 1 mile</h3>
              <Bars counts={d.counts["1mi"]} />
            </div>
            <div>
              <h3>Anchors and national chains nearby</h3>
              {d.anchors.length === 0 ? (
                <p className="muted small">No listed anchor brands within 3 miles.</p>
              ) : (
                <ul className="anchor-list">
                  {d.anchors.slice(0, 12).map((a) => (
                    <li key={a.id}>
                      <span>{placeName(a)}</span>
                      <small>{miles(a.distance_mi)}</small>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        </>
      )}
    </Panel>
  );
}

function Changes({ d }: { d: Businesses }) {
  const c = d.changes;
  if (c.reason === "NOT_ENOUGH_DATA" || !d.prior_release)
    return <p className="small muted">Changes appear once two monthly releases are stored for this pin.</p>;
  const tone = (s?: string) => (s === "High" ? "red" : s === "Watch" ? "amber" : "neutral");
  return (
    <div className="business-changes">
      <h3>
        Changes since {releaseLabel(d.prior_release)}
        <small>
          {" "}
          · {plural(c.total_closures ?? c.closures.length, "possible closure")} ·{" "}
          {plural(c.total_openings ?? c.openings.length, "new key business", "new key businesses")}
        </small>
      </h3>
      {c.broad_data_change && (
        <p className="notice">
          Overture changed broadly across many properties this release, so these changes are shown as FYI only.
        </p>
      )}
      {c.closures.length === 0 && c.openings.length === 0 ? (
        <p className="small muted">No changes to anchors or national chains nearby.</p>
      ) : (
        <ul className="change-list">
          {c.closures.slice(0, 8).map((p) => (
            <li key={p.id}>
              <span className={`badge ${tone(p.severity)}`}>{p.severity}</span>
              <div>
                <strong>Possible closure: {placeName(p)}</strong>
                <small>
                  {miles(p.distance_mi)} · {p.evidence}
                  {p.confirmed === false ? " · not yet confirmed (needs a second release)" : ""}
                  {p.tenant_match ? " · matches a tenant at this property" : ""} · verify before acting
                </small>
              </div>
            </li>
          ))}
          {c.openings.slice(0, 5).map((p) => (
            <li key={p.id}>
              <span className="badge">FYI</span>
              <div>
                <strong>New in map data: {placeName(p)}</strong>
                <small>{miles(p.distance_mi)} · may be a new opening or a data addition</small>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function Bars({ counts }: { counts: Record<string, number> }) {
  const entries = Object.entries(counts);
  const max = Math.max(1, ...entries.map(([, n]) => n));
  return (
    <ul className="bars" aria-label="Businesses within 1 mile by group">
      {entries.map(([group, n]) => (
        <li key={group}>
          <span>{group}</span>
          <span className="bar" aria-hidden="true">
            <span style={{ width: `${(n / max) * 100}%` }} />
          </span>
          <strong>{count(n)}</strong>
        </li>
      ))}
    </ul>
  );
}

function plural(n: number, one: string, many = one + "s") {
  return `${n} ${n === 1 ? one : many}`;
}

function JobsPanel({ section }: { section: Section<Jobs> }) {
  const d = section.data;
  return (
    <Panel eyebrow="DAYTIME POPULATION" title="Jobs located near the site" icon={<Building size={22} />} section={section}>
      {d && d.rings && (
        <>
          <p className="trade-meta">
            <span className="badge">Estimate</span>
            <span>
              LODES {d.year}: jobs by where people work, summed over each ring. Workers drive weekday
              lunch, convenience and service trips.
            </span>
          </p>
          <div className="table-wrap">
            <table className="ring-table">
              <caption className="sr-only">Jobs located in each ring, {d.year}</caption>
              <thead>
                <tr>
                  <th scope="col">Within</th>
                  {d.rings.map((r) => (
                    <th scope="col" key={r.radius_miles}>
                      {r.radius_miles} {r.radius_miles === 1 ? "mile" : "miles"}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {([
                  ["total", "All jobs", "Everyone working in the ring"],
                  ["retail", "Retail jobs", "NAICS 44–45"],
                  ["food_service", "Accommodation and food service jobs", "NAICS 72"],
                ] as const).map(([key, label, hint]) => (
                  <tr key={key}>
                    <th scope="row">
                      {label}
                      <small>{hint}</small>
                    </th>
                    {d.rings.map((r) => (
                      <td key={r.radius_miles}>
                        <strong>{count(r[key])}</strong>
                      </td>
                    ))}
                  </tr>
                ))}
                <tr>
                  <th scope="row">
                    Change in all jobs
                    <small>{d.prior_year ? `${d.prior_year} → ${d.year}` : "Prior year unavailable"}</small>
                  </th>
                  {d.rings.map((r) => (
                    <td key={r.radius_miles} className="trend flat">
                      <strong>{r.change_pct != null ? signedPct(r.change_pct) : "Not shown"}</strong>
                      {r.change_pct == null && <small>Needs 1,000+ jobs both years</small>}
                    </td>
                  ))}
                </tr>
              </tbody>
            </table>
          </div>
          <p className="small muted">{d.note}</p>
        </>
      )}
    </Panel>
  );
}
