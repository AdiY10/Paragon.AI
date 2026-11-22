import { useId, useMemo, useState } from "react";
import { sectionRunState } from "../../../api/analysis";
import type { AnalysisBundle } from "../../../api/types";
import { GroupedBarList } from "../../../components/charts";
import { AnalysisMap, type MapPlace } from "../../../components/map/lazy";
import { placeName, releaseLabel, type Place } from "../../../lib/format/area";
import { distanceMi, formatInt } from "../../../lib/format/numbers";
import { SectionShell } from "../SectionShell";

const toMapPlace = (p: Place, extra: Partial<MapPlace> = {}): MapPlace | null =>
  p.lat === undefined || p.lon === undefined
    ? null
    : {
        id: p.id,
        name: placeName(p),
        group: p.group,
        groupLabel: p.group,
        lat: p.lat,
        lon: p.lon,
        distance_mi: p.distance_mi,
        ...extra,
      };

/** Overture places: map with a category filter, 1 vs 3 mi counts, anchors, nearest grocer, changes. */
export function RetailSection({ bundle }: { bundle: AnalysisBundle }) {
  const section = bundle.sections.businesses;
  const d = section.data;
  const pin = bundle.location.current_revision;
  const [category, setCategory] = useState("");
  const selectId = useId();
  const groups = useMemo(() => {
    if (!d) return [] as string[];
    const all = new Set([...Object.keys(d.counts["3mi"] ?? {}), ...Object.keys(d.counts["1mi"] ?? {})]);
    return [...all].sort((a, b) => (d.counts["3mi"]?.[b] ?? 0) - (d.counts["3mi"]?.[a] ?? 0));
  }, [d]);
  const mapPlaces = useMemo(() => {
    if (!d) return { places: [] as MapPlace[], anchors: [] as MapPlace[] };
    const closures = d.changes.closures.map((p) => toMapPlace(p, { closed: true }));
    const openings = d.changes.openings.map((p) => toMapPlace(p));
    const listed = (d.places ?? []).map((p) => toMapPlace(p));
    return {
      places: [...listed, ...closures, ...openings].filter((p): p is MapPlace => !!p),
      anchors: d.anchors.map((p) => toMapPlace(p, { anchor: true })).filter((p): p is MapPlace => !!p),
    };
  }, [d]);
  const rows = groups.slice(0, 10).map((group) => ({
    key: group,
    label: group,
    values: [
      { value: d?.counts["1mi"]?.[group] ?? 0, display: formatInt(d?.counts["1mi"]?.[group] ?? 0) ?? undefined },
      { value: d?.counts["3mi"]?.[group] ?? 0, display: formatInt(d?.counts["3mi"]?.[group] ?? 0) ?? undefined },
    ],
  }));
  const c = d?.changes;
  return (
    <SectionShell
      id="retail"
      title="Retail landscape"
      run={sectionRunState(section)}
      reason={section.reason}
      stale={section.stale}
      computedAt={section.computed_at}
      sources={section.sources}
      intro={<p>Businesses listed in Overture Maps near the pin. A listing is not proof a business is open.</p>}
    >
      {d && (
        <>
          <div className="retail-grid">
            <div className="retail-map">
              <div className="field inline">
                <label htmlFor={selectId}>Highlight category</label>
                <select id={selectId} value={category} onChange={(event) => setCategory(event.target.value)}>
                  <option value="">All categories</option>
                  {groups.map((g) => (
                    <option key={g} value={g}>
                      {g}
                    </option>
                  ))}
                </select>
              </div>
              {pin.lat !== null && pin.lon !== null && (
                <AnalysisMap
                  center={[pin.lon, pin.lat]}
                  ringMiles={[1, 3]}
                  places={mapPlaces.places}
                  anchors={mapPlaces.anchors}
                  category={category || null}
                  label="Map of nearby businesses"
                  subjectLabel={`${bundle.location.name} pin`}
                  textAlternativeId="retail-list"
                  placesSource={`Overture Maps places, ${releaseLabel(d.release)}`}
                />
              )}
              {!d.places && (
                <p className="fine-print">The map shows anchors and recent changes; every business is counted in the list.</p>
              )}
            </div>
            <div className="retail-facts">
              <h3>Nearest supermarket</h3>
              <p className="big-fact">
                {d.nearest_supermarket
                  ? `${placeName(d.nearest_supermarket)} · ${distanceMi(d.nearest_supermarket.distance_mi)}`
                  : "None listed within 3 mi"}
              </p>
              <h3>Retail and services</h3>
              <p>
                {formatInt(d.retail_and_services_total["1mi"]) ?? "—"} within 1 mi ·{" "}
                {formatInt(d.retail_and_services_total["3mi"]) ?? "—"} within 3 mi
              </p>
              <h3>Anchors and national chains</h3>
              {d.anchors.length ? (
                <ul className="anchor-list-v2">
                  {d.anchors.slice(0, 10).map((a) => (
                    <li key={a.id}>
                      <span>{placeName(a)}</span>
                      <small>
                        {a.group} · {distanceMi(a.distance_mi)}
                      </small>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="fine-print">No named anchors within 3 mi.</p>
              )}
            </div>
          </div>
          <div className="subsection">
            <h3>Businesses by category, within 1 and 3 mi</h3>
            <GroupedBarList label="Businesses by category" series={["Within 1 mi", "Within 3 mi"]} rows={rows} />
          </div>
          {c && (
            <div className="subsection">
              <h3>Recent changes{d.prior_release ? ` since ${releaseLabel(d.prior_release)}` : ""}</h3>
              {c.reason === "NOT_ENOUGH_DATA" || !d.prior_release ? (
                <p className="fine-print">Changes appear once two monthly releases are stored for this location.</p>
              ) : c.closures.length + c.openings.length === 0 ? (
                <p className="fine-print">No changes to anchors or national chains nearby.</p>
              ) : (
                <ul className="change-list">
                  {c.closures.slice(0, 3).map((p) => (
                    <li key={p.id}>
                      <strong>Possible closure: {placeName(p)}</strong>
                      <small>
                        {distanceMi(p.distance_mi)}
                        {p.evidence ? ` · ${p.evidence}` : ""} · verify before acting
                      </small>
                    </li>
                  ))}
                  {c.openings.slice(0, 3).map((p) => (
                    <li key={p.id}>
                      <strong>Possible opening: {placeName(p)}</strong>
                      <small>{distanceMi(p.distance_mi)} · may be a new opening or a data addition</small>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
          <details className="full-list" id="retail-list">
            <summary>All categories with counts</summary>
            <table className="data-table">
              <caption className="sr-only">Businesses by category</caption>
              <thead>
                <tr>
                  <th scope="col">Category</th>
                  <th scope="col" className="num">
                    Within 1 mi
                  </th>
                  <th scope="col" className="num">
                    Within 3 mi
                  </th>
                </tr>
              </thead>
              <tbody>
                {groups.map((g) => (
                  <tr key={g}>
                    <th scope="row">{g}</th>
                    <td className="num">{formatInt(d.counts["1mi"]?.[g] ?? 0)}</td>
                    <td className="num">{formatInt(d.counts["3mi"]?.[g] ?? 0)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </details>
        </>
      )}
    </SectionShell>
  );
}
