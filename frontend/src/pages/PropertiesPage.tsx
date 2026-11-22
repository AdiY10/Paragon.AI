import { useMemo, useState } from "react";
import { navigate, parseHash, useQueryState } from "../app/router";
import { PortfolioMap } from "../components/map/lazy";
import { EmptyState } from "../components/ui/EmptyState";
import { LiveRegion } from "../components/ui/LiveRegion";
import { LIMIT_MESSAGE, useCompareSelection } from "../features/compare/selection";
import { CompareTray } from "../features/properties/CompareTray";
import { PropertiesTable } from "../features/properties/PropertiesTable";
import { PropertiesToolbar } from "../features/properties/PropertiesToolbar";
import { PropertyList } from "../features/properties/PropertyList";
import {
  attentionCounts,
  DEFAULT_DIR,
  filterProperties,
  isSortKey,
  sortProperties,
  type SortDir,
  type SortKey,
} from "../lib/properties";
import type { Location } from "../types";

const TABLE_ID = "properties-table";

/** Updates several query parameters in one history replacement (no focus move). */
function setQuery(changes: Record<string, string>) {
  const { path, query } = parseHash(window.location.hash);
  for (const [key, value] of Object.entries(changes)) {
    if (value) query.set(key, value);
    else query.delete(key);
  }
  const q = query.toString();
  navigate(path + (q ? "?" + q : ""), { replace: true });
}

/** `#/`: map of every owned property, then the sortable table (cards on phones). */
export function PropertiesPage({ locations }: { locations: Location[] }) {
  const [q] = useQueryState("q");
  const [state] = useQueryState("state");
  const [attention] = useQueryState("attention");
  const [sortParam] = useQueryState("sort");
  const [dirParam] = useQueryState("dir");
  const sort: SortKey = isSortKey(sortParam) ? sortParam : "attention";
  const dir: SortDir = dirParam === "asc" || dirParam === "desc" ? dirParam : DEFAULT_DIR[sort];
  const [highlightId, setHighlightId] = useState<string | null>(null);
  const [announcement, setAnnouncement] = useState("");
  const compare = useCompareSelection();

  const owned = useMemo(() => locations.filter((l) => l.status === "owned"), [locations]);
  const counts = useMemo(() => attentionCounts(owned), [owned]);
  const states = useMemo(() => [...new Set(owned.map((l) => l.state).filter(Boolean))].sort(), [owned]);
  const filtered = useMemo(() => filterProperties(owned, { q, state, attention }), [owned, q, state, attention]);
  const rows = useMemo(() => sortProperties(filtered, sort, dir), [filtered, sort, dir]);
  const filteredKey = filtered.map((l) => l.id).join(",");
  // A new Set only when the filtered ids change, so the map re-fits on filter changes only.
  const visibleIds = useMemo(() => new Set(filteredKey ? filteredKey.split(",") : []), [filteredKey]);
  const byId = useMemo(() => new Map(locations.map((l) => [l.id, l])), [locations]);
  const trayItems = compare.ids.map((id) => ({ id, name: byId.get(id)?.name ?? "Analyzed place" }));

  const onSort = (key: SortKey) => {
    const nextDir = key === sort ? (dir === "asc" ? "desc" : "asc") : DEFAULT_DIR[key];
    setQuery({ sort: key === "attention" && nextDir === "asc" ? "" : key, dir: nextDir === DEFAULT_DIR[key] ? "" : nextDir });
  };
  const onToggleCompare = (id: string) => {
    const name = byId.get(id)?.name ?? "Property";
    const wasSelected = compare.ids.includes(id);
    if (!compare.toggle(id)) setAnnouncement(LIMIT_MESSAGE);
    else setAnnouncement(wasSelected ? `${name} removed from compare.` : `${name} added to compare.`);
  };
  const attentionLink = (level: "High" | "Watch") => (
    <button
      type="button"
      className="count-link"
      aria-pressed={attention === level}
      onClick={() => setQuery({ attention: attention === level ? "" : level })}
    >
      {counts[level]} {level}
    </button>
  );

  return (
    <div className={compare.ids.length ? "properties-page has-tray" : "properties-page"}>
      <header className="page-header">
        <h1>Properties</h1>
        <p className="page-counts">
          <button
            type="button"
            className="count-link"
            aria-pressed={!q && !state && !attention}
            onClick={() => setQuery({ q: "", state: "", attention: "" })}
          >
            {owned.length} owned
          </button>
          <span aria-hidden="true"> · </span>
          {attentionLink("High")}
          <span aria-hidden="true"> · </span>
          {attentionLink("Watch")}
        </p>
      </header>
      <PropertiesToolbar
        q={q}
        state={state}
        attention={attention}
        states={states}
        shown={filtered.length}
        total={owned.length}
        onChange={(key, value) => setQuery({ [key]: value })}
        onClear={() => setQuery({ q: "", state: "", attention: "" })}
      />
      <section className="properties-map" aria-label="Map">
        <PortfolioMap
          locations={owned}
          visibleIds={visibleIds}
          highlightId={highlightId}
          onHover={setHighlightId}
          onSelect={(id) => navigate("/p/" + id)}
          textAlternativeId={TABLE_ID}
        />
      </section>
      {rows.length ? (
        <>
          <PropertiesTable
            id={TABLE_ID}
            rows={rows}
            sort={sort}
            dir={dir}
            onSort={onSort}
            selected={compare.ids}
            full={compare.full}
            onToggleCompare={onToggleCompare}
            highlightId={highlightId}
            onHighlight={setHighlightId}
          />
          <PropertyList
            rows={rows}
            sort={sort}
            dir={dir}
            onSortChange={(key, d) => setQuery({ sort: key === "attention" && d === "asc" ? "" : key, dir: d === DEFAULT_DIR[key] ? "" : d })}
            selected={compare.ids}
            full={compare.full}
            onToggleCompare={onToggleCompare}
          />
        </>
      ) : (
        <EmptyState
          title="No properties match these filters."
          action={
            <button type="button" className="btn btn-secondary btn-sm" onClick={() => setQuery({ q: "", state: "", attention: "" })}>
              Clear filters
            </button>
          }
        >
          Change the search or filters to see more properties.
        </EmptyState>
      )}
      <p className="properties-note">
        Figures describe the area around each property (radius rings, county, nearest road), not the property itself.
      </p>
      <CompareTray items={trayItems} onRemove={compare.remove} onClear={compare.clear} />
      <LiveRegion message={announcement} />
    </div>
  );
}
