import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { clusterPoints } from "../../lib/cluster";
import { formatInt, formatUsd } from "../../lib/format/numbers";
import type { Location } from "../../types";
import { AttentionBadge, type Attention } from "../ui/Badge";
import { Missing } from "../ui/Stat";
import { MapFrame } from "./MapFrame";
import { MapPopup } from "./MapPopup";
import { maplibregl, type MapLibreMap, type Marker } from "./maplibre";
import { useMapLibre } from "./useMapLibre";

const CLUSTER_RADIUS = 40;
/** Past this zoom, pins that still overlap share a building: show them all instead of a cluster. */
const NO_CLUSTER_ZOOM = 15;

type Pinned = Location & { current_revision: { lat: number; lon: number } };
const isPinned = (l: Location): l is Pinned => l.current_revision.lat !== null && l.current_revision.lon !== null;
const attentionOf = (l: Location): Attention => l.attention ?? "Clear";
const ATTENTION_RANK: Record<Attention, number> = { High: 0, Watch: 1, Clear: 2 };

function pinLabel(l: Location) {
  const place = [l.city, l.state].filter(Boolean).join(", ");
  return `${l.name}${place ? ", " + place : ""}. ${attentionOf(l)} attention. Open analysis`;
}
function boundsOf(items: Pinned[]): [[number, number], [number, number]] | null {
  if (!items.length) return null;
  let minLon = 180,
    minLat = 90,
    maxLon = -180,
    maxLat = -90;
  for (const l of items) {
    const { lat, lon } = l.current_revision;
    minLon = Math.min(minLon, lon);
    maxLon = Math.max(maxLon, lon);
    minLat = Math.min(minLat, lat);
    maxLat = Math.max(maxLat, lat);
  }
  return [
    [minLon, minLat],
    [maxLon, maxLat],
  ];
}

function makePin(l: Location) {
  const el = document.createElement("button");
  el.type = "button";
  el.className = "map-marker portfolio-pin";
  const shape = document.createElement("span");
  shape.className = "pin-shape";
  shape.setAttribute("aria-hidden", "true");
  el.append(shape);
  updatePin(el, l);
  return el;
}
function updatePin(el: HTMLElement, l: Location) {
  const level = attentionOf(l).toLowerCase();
  el.dataset.attention = level;
  el.dataset.id = l.id;
  el.setAttribute("aria-label", pinLabel(l));
  const shape = el.firstElementChild as HTMLElement;
  shape.textContent = level === "clear" ? "" : "!";
}

/**
 * All owned properties as HTML button pins (focusable, labelled, ≥24 px targets) with
 * screen-space clustering. Markers are created once per id; filtering toggles `hidden`; the view
 * re-fits (debounced) only when the filter changes. Hover or focus shows one reused card.
 */
export function PortfolioMap({
  locations,
  visibleIds = null,
  highlightId = null,
  onHover,
  onSelect,
  textAlternativeId,
  label = "Map of owned properties",
}: {
  locations: Location[];
  /** Ids that pass the page filters; null = all. */
  visibleIds?: ReadonlySet<string> | null;
  highlightId?: string | null;
  onHover?: (id: string | null) => void;
  onSelect: (id: string) => void;
  textAlternativeId?: string;
  label?: string;
}) {
  const pinned = useMemo(() => locations.filter(isPinned), [locations]);
  const byId = useMemo(() => new Map(pinned.map((l) => [l.id, l])), [pinned]);
  const initialBounds = useRef(boundsOf(pinned));
  const [el, setEl] = useState<HTMLDivElement | null>(null);
  const { map, ready, failed, tileUrl } = useMapLibre(el, {
    bounds: initialBounds.current,
    padding: 56,
    zoom: pinned.length === 1 ? 11 : undefined,
    center: pinned.length === 1 ? [pinned[0].current_revision.lon, pinned[0].current_revision.lat] : undefined,
  });
  const markers = useRef(new Map<string, { marker: Marker; el: HTMLButtonElement }>());
  const clusters = useRef(new Map<string, { marker: Marker; el: HTMLButtonElement; ids: string[] }>());
  const clusteredIds = useRef(new Set<string>());
  const [card, setCard] = useState<string | null>(null);
  const hideTimer = useRef<number | undefined>(undefined);
  const lastPointer = useRef<string>("mouse");
  const latest = useRef({ onSelect, onHover, byId, card, highlightId });
  latest.current = { onSelect, onHover, byId, card, highlightId };

  const showCard = useCallback((id: string | null) => {
    window.clearTimeout(hideTimer.current);
    setCard(id);
    latest.current.onHover?.(id);
  }, []);
  const hideCardSoon = useCallback(() => {
    window.clearTimeout(hideTimer.current);
    hideTimer.current = window.setTimeout(() => {
      setCard(null);
      latest.current.onHover?.(null);
    }, 160);
  }, []);
  useEffect(() => () => window.clearTimeout(hideTimer.current), []);

  function applyHighlight() {
    const id = latest.current.highlightId;
    for (const [pinId, { el: pin }] of markers.current) pin.classList.toggle("is-highlighted", pinId === id);
    for (const entry of clusters.current.values())
      entry.el.classList.toggle("is-highlighted", !!id && entry.ids.includes(id));
  }
  const isVisible = useCallback((id: string) => !visibleIds || visibleIds.has(id), [visibleIds]);

  const recluster = useCallback(() => {
    if (!map) return;
    const shown = pinned.filter((l) => isVisible(l.id));
    const groups =
      map.getZoom() >= NO_CLUSTER_ZOOM
        ? shown.map((l) => ({ key: l.id, ids: [l.id], x: 0, y: 0 }))
        : clusterPoints(
            shown.map((l) => {
              const p = map.project([l.current_revision.lon, l.current_revision.lat]);
              return { id: l.id, x: p.x, y: p.y };
            }),
            CLUSTER_RADIUS,
          );
    const nextClustered = new Set<string>();
    const keep = new Set<string>();
    for (const group of groups) {
      if (group.ids.length < 2) continue;
      group.ids.forEach((id) => nextClustered.add(id));
      keep.add(group.key);
      const members = group.ids.map((id) => latest.current.byId.get(id)!);
      const lon = members.reduce((s, m) => s + m.current_revision.lon, 0) / members.length;
      const lat = members.reduce((s, m) => s + m.current_revision.lat, 0) / members.length;
      const worst = members.map(attentionOf).sort((a, b) => ATTENTION_RANK[a] - ATTENTION_RANK[b])[0];
      const high = members.filter((m) => attentionOf(m) === "High").length;
      const watch = members.filter((m) => attentionOf(m) === "Watch").length;
      const flagged = [high && `${high} High`, watch && `${watch} Watch`].filter(Boolean).join(", ");
      const names = members.map((m) => m.name).join(", ");
      let entry = clusters.current.get(group.key);
      if (!entry) {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "map-cluster";
        button.addEventListener("click", () => {
          const b = new maplibregl.LngLatBounds();
          for (const m of members) b.extend([m.current_revision.lon, m.current_revision.lat]);
          map.fitBounds(b, { padding: 80, maxZoom: NO_CLUSTER_ZOOM + 1, duration: 400 });
        });
        entry = { marker: new maplibregl.Marker({ element: button }).setLngLat([lon, lat]).addTo(map), el: button, ids: group.ids };
        clusters.current.set(group.key, entry);
      }
      entry.marker.setLngLat([lon, lat]);
      entry.el.textContent = String(members.length);
      entry.el.dataset.attention = worst.toLowerCase();
      entry.el.setAttribute(
        "aria-label",
        `${members.length} properties${flagged ? ` (${flagged})` : ""}: ${names}. Zoom in`,
      );
    }
    for (const [key, entry] of clusters.current)
      if (!keep.has(key)) {
        entry.marker.remove();
        clusters.current.delete(key);
      }
    clusteredIds.current = nextClustered;
    for (const [id, { el: pin }] of markers.current) pin.hidden = !isVisible(id) || nextClustered.has(id);
    applyHighlight();
    if (latest.current.card && (nextClustered.has(latest.current.card) || !isVisible(latest.current.card)))
      setCard(null);
  }, [map, pinned, isVisible]);

  // Create / update / remove markers when the pinned set changes (never on filter or hover).
  const markersMap = useRef<MapLibreMap | null>(null);
  useEffect(() => {
    if (!map) return;
    if (markersMap.current !== map) {
      // A new map (remount): the old markers went with the old map.
      markers.current.clear();
      clusters.current.clear();
      markersMap.current = map;
    }
    const seen = new Set<string>();
    for (const l of pinned) {
      seen.add(l.id);
      const existing = markers.current.get(l.id);
      if (existing) {
        existing.marker.setLngLat([l.current_revision.lon, l.current_revision.lat]);
        updatePin(existing.el, l);
        continue;
      }
      const pin = makePin(l);
      pin.addEventListener("pointerdown", (event) => (lastPointer.current = event.pointerType));
      pin.addEventListener("pointerenter", (event) => {
        if (event.pointerType === "mouse") showCard(l.id);
      });
      pin.addEventListener("pointerleave", (event) => {
        if (event.pointerType === "mouse") hideCardSoon();
      });
      pin.addEventListener("focus", () => showCard(l.id));
      pin.addEventListener("blur", hideCardSoon);
      pin.addEventListener("click", () => {
        // Touch: the first tap shows the card, the second opens the analysis.
        if (lastPointer.current === "touch" && latest.current.card !== l.id) {
          showCard(l.id);
          return;
        }
        latest.current.onSelect(l.id);
      });
      const marker = new maplibregl.Marker({ element: pin }).setLngLat([l.current_revision.lon, l.current_revision.lat]).addTo(map);
      markers.current.set(l.id, { marker, el: pin });
    }
    for (const [id, entry] of markers.current)
      if (!seen.has(id)) {
        entry.marker.remove();
        markers.current.delete(id);
      }
    recluster();
  }, [map, pinned, recluster, showCard, hideCardSoon]);


  // Recluster on zoom and resize.
  useEffect(() => {
    if (!map) return;
    map.on("zoomend", recluster);
    map.on("resize", recluster);
    return () => {
      map.off("zoomend", recluster);
      map.off("resize", recluster);
    };
  }, [map, recluster]);

  // Filter change: toggle visibility now, re-fit after a short pause.
  const firstFilter = useRef(true);
  useEffect(() => {
    if (!map) return;
    recluster();
    if (firstFilter.current) {
      firstFilter.current = false;
      return;
    }
    const timer = window.setTimeout(() => {
      const shown = pinned.filter((l) => isVisible(l.id));
      const b = boundsOf(shown);
      if (!b) return;
      if (shown.length === 1) map.easeTo({ center: b[0], zoom: 11, duration: 400 });
      else map.fitBounds(b, { padding: 56, maxZoom: 12, duration: 400 });
    }, 250);
    return () => window.clearTimeout(timer);
  }, [map, visibleIds, pinned, isVisible, recluster]);

  // Row hover/focus highlights the pin (or the cluster that holds it).
  useEffect(applyHighlight, [highlightId]);

  const active = card ? byId.get(card) : undefined;
  const numbers = active?.key_numbers ?? {};
  return (
    <MapFrame
      containerRef={setEl}
      label={label}
      textAlternativeId={textAlternativeId}
      ready={ready}
      failed={failed}
      tileUrl={tileUrl}
      pins={pinned.length}
      className="portfolio-map-frame"
      overlay={
        active && (
          <MapPopup
            map={map}
            lngLat={[active.current_revision.lon, active.current_revision.lat]}
            label={active.name}
            className="hover-card"
            onPointerEnter={() => showCard(active.id)}
            onPointerLeave={hideCardSoon}
          >
            <div className="hover-card-head">
              <strong>{active.name}</strong>
              <AttentionBadge level={active.attention} />
            </div>
            <small>{[active.city, active.state].filter(Boolean).join(", ")}</small>
            <dl className="hover-card-numbers">
              <dt>People within 3 mi</dt>
              <dd>{formatInt(numbers.population) ?? <Missing />}</dd>
              <dt>Median household income</dt>
              <dd>{formatUsd(numbers.median_household_income) ?? <Missing />}</dd>
              <dt>Main-road traffic</dt>
              <dd>{numbers.aadt != null ? `${formatInt(numbers.aadt)}/day` : <Missing />}</dd>
              <dt>Active alerts</dt>
              <dd>{formatInt(numbers.active_alerts) ?? <Missing />}</dd>
            </dl>
            <a className="hover-card-link" href={"#/p/" + active.id} tabIndex={-1}>
              Open analysis
            </a>
          </MapPopup>
        )
      }
      below={<PinLegend />}
    />
  );
}

/** HTML legend for attention pins (shape + word, never colour alone). */
export function PinLegend() {
  return (
    <ul className="pin-legend" aria-label="Map legend">
      <li>
        <span className="legend-pin" data-attention="high" aria-hidden="true">
          <span className="pin-shape">!</span>
        </span>
        High attention
      </li>
      <li>
        <span className="legend-pin" data-attention="watch" aria-hidden="true">
          <span className="pin-shape">!</span>
        </span>
        Watch
      </li>
      <li>
        <span className="legend-pin" data-attention="clear" aria-hidden="true">
          <span className="pin-shape" />
        </span>
        Clear
      </li>
      <li>
        <span className="legend-cluster" aria-hidden="true">
          4
        </span>
        Several properties: zoom in
      </li>
    </ul>
  );
}
export type { MapLibreMap };
