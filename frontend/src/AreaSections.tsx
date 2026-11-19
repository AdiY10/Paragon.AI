import { useEffect, useState, type ReactNode } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Briefcase, Car, RefreshCw, ShieldAlert } from "lucide-react";
import { api, dateLabel } from "./api";
import type { Location } from "./types";
import { reasonText } from "./demographics";
import {
  count,
  floodHeadline,
  floodTone,
  money,
  monthLabel,
  pct,
  signedPct,
  signedPts,
  type Area,
  type Economy,
  type Hazards,
  type Section,
  type SourceRef,
  type Traffic,
} from "./area";

const POLL_MS = 4000;
const POLL_LIMIT_MS = 240_000;

export default function AreaSections({ location }: { location: Location }) {
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
            ? "The pin moved. Re-check economy, traffic and hazards for the new location."
            : "Economy, traffic and hazards have not been checked for this location yet."}
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
          <RefreshCw size={15} /> Check economy, traffic and hazards
        </button>
      )}
    </div>
  );

  return (
    <>
      {action && <section className="panel">{action}</section>}
      <EconomyPanel section={sections.economy} />
      <div className="location-columns">
        <TrafficPanel section={sections.traffic} />
        <HazardsPanel section={sections.hazards} />
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
            · {monthLabel(s.period)} · retrieved {dateLabel(s.retrieved_at)}
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
                  ? `${signedPct(d.employment.private.yoy_pct, d.employment.private.yoy_reason)} vs a year earlier`
                  : reasonText(d.employment.private?.reason ?? d.employment.reason)
              }
              note={d.employment.period}
            />
            <Stat
              label="Retail jobs"
              value={count(d.employment.retail?.value)}
              detail={
                d.employment.retail?.value != null
                  ? `${signedPct(d.employment.retail.yoy_pct, d.employment.retail.yoy_reason)} vs a year earlier`
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
                    {[r.road_class, r.lanes ? `${r.lanes} lanes` : null].filter(Boolean).join(" · ")}
                  </small>
                </div>
                <div className="road-count">
                  <strong>{count(r.aadt)}</strong>
                  <small>vehicles/day · {r.year}</small>
                  <small>
                    {r.change_pct != null
                      ? `${signedPct(r.change_pct)} vs ${r.prior_year}`
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
            {d.flood_nearby.zone && d.flood_nearby.zone !== d.flood_at_pin.zone && (
              <>
                <dt>Within ~100 m</dt>
                <dd>
                  <span className={`badge ${floodTone(d.flood_nearby)}`}>{floodHeadline(d.flood_nearby)}</span>
                </dd>
              </>
            )}
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
