import React, { lazy, Suspense, useState } from "react";
import { ArrowUpRight, Building2, MapPin, SlidersHorizontal } from "lucide-react";
import { type Location } from "../types";
import { hashParams, titleCase, Badge, Empty, PageHead } from "../components/ui";
import { AddLocation } from "../components/LocationForms";

const LocationMap = lazy(() => import("../LocationMap"));

export const rankAttention = (l: Location) => (l.attention === "High" ? 0 : l.attention === "Watch" ? 1 : 2);
export function PropertyCard({ location }: { location: Location }) {
  return (
    <a className="property-card" href={"#/locations/" + location.id}>
      <div className="card-top">
        <span className="property-icon">
          <Building2 size={22} />
        </span>
        <span className="card-badges">
          {location.attention && location.attention !== "Clear" && (
            <Badge tone={location.attention === "High" ? "red" : "amber"}>{location.attention}</Badge>
          )}
          <Badge tone={location.confirmed ? "green" : "unverified"}>
            {location.confirmed ? "Confirmed" : "Unconfirmed"}
          </Badge>
        </span>
      </div>
      <span className="eyebrow">
        {location.state} · {titleCase(location.asset_type)}
      </span>
      <h3>{location.name}</h3>
      <p>{location.address}</p>
      {location.key_numbers && Object.keys(location.key_numbers).length > 0 && (
        <dl className="card-numbers">
          {location.key_numbers.population != null && (
            <div>
              <dt>People, 3 mi</dt>
              <dd>{Math.round(location.key_numbers.population).toLocaleString("en-US")}</dd>
            </div>
          )}
          {location.key_numbers.median_household_income != null && (
            <div>
              <dt>Median income</dt>
              <dd>${Math.round(location.key_numbers.median_household_income / 1000)}k</dd>
            </div>
          )}
          {location.key_numbers.aadt != null && (
            <div>
              <dt>Traffic/day</dt>
              <dd>{Math.round(location.key_numbers.aadt).toLocaleString("en-US")}</dd>
            </div>
          )}
        </dl>
      )}
      <div className="card-bottom">
        <span>
          <MapPin size={14} />
          {location.current_revision.lat === null ? "Pin needed" : location.city ? `${location.city}, ${location.state}` : "Pin placed"}
        </span>
        <ArrowUpRight size={18} />
      </div>
    </a>
  );
}
export function Portfolio({
  locations,
  candidates = false,
}: {
  locations: Location[];
  candidates?: boolean;
}) {
  const params = candidates ? new URLSearchParams() : hashParams();
  const [state, setState] = useState(params.get("state") ?? ""),
    [status, setStatus] = useState(candidates ? "candidate" : (params.get("status") ?? "owned")),
    [type, setType] = useState(params.get("type") ?? ""),
    [attention, setAttention] = useState(params.get("attention") ?? ""),
    [onlyUnconfirmed] = useState(params.get("confirmed") === "no"),
    [showMap, setShowMap] = useState(!candidates);
  React.useEffect(() => {
    if (candidates) return;
    const q = new URLSearchParams();
    if (state) q.set("state", state);
    if (status !== "owned") q.set("status", status);
    if (type) q.set("type", type);
    if (attention) q.set("attention", attention);
    if (onlyUnconfirmed) q.set("confirmed", "no");
    const next = "#/portfolio" + (q.toString() ? "?" + q.toString() : "");
    if (window.location.hash !== next) window.history.replaceState(null, "", next);
  }, [candidates, state, status, type, attention, onlyUnconfirmed]);
  const filtered = locations.filter(
    (item) =>
      (!state || item.state === state) &&
      (!status || item.status === status) &&
      (!type || item.asset_type === type) &&
      (!attention || (item.attention ?? "Clear") === attention) &&
      (!onlyUnconfirmed || !item.confirmed),
  ).sort((a, b) => rankAttention(a) - rankAttention(b) || a.name.localeCompare(b.name));
  return (
    <>
      {!candidates && (
        <PageHead
          eyebrow="Location management"
          title="The portfolio."
          description="Your locations, their source records, and what still needs confirming."
          action={<AddLocation />}
        />
      )}
      <div className="filterbar">
        <span>
          <SlidersHorizontal size={17} />
          {filtered.length} locations
        </span>
        <label>
          State
          <select
            aria-label="State"
            value={state}
            onChange={(e) => setState(e.target.value)}
          >
            <option value="">All states</option>
            {[...new Set(locations.map((l) => l.state).filter(Boolean))]
              .sort()
              .map((s) => (
                <option key={s}>{s}</option>
              ))}
          </select>
        </label>
        {!candidates && (
          <label>
            Status
            <select
              aria-label="Status"
              value={status}
              onChange={(e) => setStatus(e.target.value)}
            >
              <option value="owned">Owned</option>
              <option value="candidate">Candidates</option>
              <option value="archived">Archived</option>
              <option value="">All statuses</option>
            </select>
          </label>
        )}
        <label>
          Asset type
          <select
            aria-label="Asset type"
            value={type}
            onChange={(e) => setType(e.target.value)}
          >
            <option value="">All types</option>
            {[...new Set(locations.map((l) => l.asset_type))]
              .sort()
              .map((t) => (
                <option value={t} key={t}>
                  {titleCase(t)}
                </option>
              ))}
          </select>
        </label>
        <label>
          Attention
          <select aria-label="Attention" value={attention} onChange={(e) => setAttention(e.target.value)}>
            <option value="">Any attention</option>
            <option value="High">High</option>
            <option value="Watch">Watch</option>
            <option value="Clear">Clear</option>
          </select>
        </label>
      </div>
      <div className="map-toolbar">
        <span>Explore saved locations</span>
        <button
          className="button secondary small-button"
          aria-pressed={showMap}
          onClick={() => setShowMap(!showMap)}
        >
          {showMap ? "List only" : "Map + list"}
          <MapPin size={15} />
        </button>
      </div>
      {showMap && (
        <section className="portfolio-map panel">
          <Suspense
            fallback={<p className="notice">Loading interactive map…</p>}
          >
            <LocationMap locations={filtered} />
          </Suspense>
        </section>
      )}
      <div className="property-grid portfolio-grid">
        {filtered.map((item) => (
          <PropertyCard key={item.id} location={item} />
        ))}
      </div>
      {!filtered.length && (
        <section className="panel">
          <Empty title="No matching locations">
            Change the filters or add a location record.
          </Empty>
        </section>
      )}
      <p className="source-note">
        Publicly listed properties remain unconfirmed until reviewed. Pins and
        area data have separate verification requirements.
      </p>
    </>
  );
}
