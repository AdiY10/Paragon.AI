import { useEffect, useMemo, useRef, useState } from "react";
import type { Feature, FeatureCollection, Geometry, MultiPolygon, Polygon } from "geojson";
import { circleCoordinates } from "../../geography";
import { distanceMi } from "../../lib/format/numbers";
import { MapFrame } from "./MapFrame";
import { MapPopup } from "./MapPopup";
import { maplibregl, type GeoJSONSource, type MapLibreMap } from "./maplibre";
import { useMapLibre } from "./useMapLibre";

export interface MapPlace {
  id: string;
  name: string;
  /** Category group used by the retail filter, e.g. "grocery". */
  group: string;
  /** Human label for the group, e.g. "Grocery". */
  groupLabel?: string;
  lat: number;
  lon: number;
  distance_mi?: number | null;
  anchor?: boolean;
  /** Confirmed closure: drawn hollow red. */
  closed?: boolean;
}
export type FloodShape = Feature<Polygon | MultiPolygon> | FeatureCollection<Polygon | MultiPolygon> | null;
export interface AnalysisLayers {
  rings?: boolean;
  places?: boolean;
  flood?: boolean;
}

const ACCENT = "#0E6B4F";
const FADED = "#94A3B8";
const CLOSED = "#C81E1E";
const EMPTY: FeatureCollection = { type: "FeatureCollection", features: [] };

/** Mount the map only once its frame scrolls near the viewport. */
function useNearViewport(el: Element | null, enabled: boolean) {
  const [near, setNear] = useState(!enabled);
  useEffect(() => {
    if (!enabled || near || !el) return;
    if (typeof IntersectionObserver === "undefined") {
      setNear(true);
      return;
    }
    const observer = new IntersectionObserver((entries) => {
      if (entries.some((entry) => entry.isIntersecting)) setNear(true);
    }, { rootMargin: "240px" });
    observer.observe(el);
    return () => observer.disconnect();
  }, [el, enabled, near]);
  return near;
}

function ringFeatures(center: [number, number], miles: number[]): FeatureCollection<Polygon> {
  return {
    type: "FeatureCollection",
    features: [...miles]
      .sort((a, b) => b - a)
      .map((m) => ({
        type: "Feature",
        properties: { miles: m },
        geometry: { type: "Polygon", coordinates: [circleCoordinates(center[0], center[1], m)] },
      })),
  };
}
function placeFeatures(places: MapPlace[], anchors: MapPlace[]): FeatureCollection {
  const anchorIds = new Set(anchors.map((a) => a.id));
  const all = [...places, ...anchors.filter((a) => !places.some((p) => p.id === a.id))];
  return {
    type: "FeatureCollection",
    features: all.map((p) => ({
      type: "Feature",
      properties: {
        id: p.id,
        group: p.group,
        anchor: p.anchor || anchorIds.has(p.id) ? 1 : 0,
        closed: p.closed ? 1 : 0,
      },
      geometry: { type: "Point", coordinates: [p.lon, p.lat] },
    })),
  };
}
const asCollection = (flood: FloodShape): FeatureCollection<Geometry> =>
  !flood ? EMPTY : flood.type === "FeatureCollection" ? flood : { type: "FeatureCollection", features: [flood] };

function placePaint(category: string | null | undefined) {
  const selected = category ? ["==", ["get", "group"], category] : true;
  return {
    "circle-radius": ["case", ["==", ["get", "anchor"], 1], 6.5, 4],
    "circle-color": ["case", ["==", ["get", "closed"], 1], "#FFFFFF", selected, ACCENT, FADED],
    "circle-opacity": category ? ["case", selected, 1, 0.45] : 0.9,
    "circle-stroke-color": ["case", ["==", ["get", "closed"], 1], CLOSED, "#FFFFFF"],
    "circle-stroke-width": ["case", ["==", ["get", "closed"], 1], 2, 1],
  } as const;
}

/**
 * The analysis map: subject pin, dashed radius rings, nearby businesses as circles (selected
 * category in accent, others faded slate, anchors larger, closures hollow red) and an optional
 * flood polygon. Layer toggles are checkboxes outside the map. Data updates use setData /
 * setPaintProperty; the map is never rebuilt.
 */
export function AnalysisMap({
  center,
  ringMiles,
  anchors = [],
  places = [],
  category = null,
  flood = null,
  layers,
  onPlaceSelect,
  label = "Map of the property, its radius rings and nearby businesses",
  subjectLabel = "Property location",
  textAlternativeId,
  placesSource = "Overture Maps places",
  lazy = true,
}: {
  center: [number, number];
  ringMiles: number[];
  anchors?: MapPlace[];
  places?: MapPlace[];
  category?: string | null;
  flood?: FloodShape;
  layers?: AnalysisLayers;
  onPlaceSelect?: (id: string) => void;
  label?: string;
  subjectLabel?: string;
  textAlternativeId?: string;
  /** Shown in the place popup. */
  placesSource?: string;
  /** Mount only when scrolled into view. */
  lazy?: boolean;
}) {
  const [frame, setFrame] = useState<HTMLDivElement | null>(null);
  const near = useNearViewport(frame, lazy);
  const [el, setEl] = useState<HTMLDivElement | null>(null);
  const largest = Math.max(0, ...ringMiles);
  const initialBounds = useMemo(() => {
    if (!largest) return null;
    const ring = circleCoordinates(center[0], center[1], largest, 32);
    const lons = ring.map((p) => p[0]),
      lats = ring.map((p) => p[1]);
    return [
      [Math.min(...lons), Math.min(...lats)],
      [Math.max(...lons), Math.max(...lats)],
    ] as [[number, number], [number, number]];
    // Initial view only.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  const { map, ready, failed, tileUrl } = useMapLibre(near ? el : null, {
    bounds: initialBounds,
    padding: 24,
    center,
    zoom: 13,
  });
  const [visible, setVisible] = useState({
    rings: layers?.rings ?? true,
    places: layers?.places ?? true,
    flood: layers?.flood ?? true,
  });
  const [selected, setSelected] = useState<MapPlace | null>(null);
  const allPlaces = useMemo(() => {
    const byId = new Map<string, MapPlace>();
    for (const p of places) byId.set(p.id, p);
    for (const a of anchors) byId.set(a.id, { ...byId.get(a.id), ...a, anchor: true });
    return byId;
  }, [places, anchors]);
  const latest = useRef({ allPlaces, onPlaceSelect });
  latest.current = { allPlaces, onPlaceSelect };

  // Sources, layers and the subject marker, once per map.
  useEffect(() => {
    if (!map || !ready) return;
    map.addSource("flood", { type: "geojson", data: EMPTY });
    map.addLayer({ id: "flood-fill", type: "fill", source: "flood", paint: { "fill-color": CLOSED, "fill-opacity": 0.14 } });
    map.addLayer({ id: "flood-line", type: "line", source: "flood", paint: { "line-color": CLOSED, "line-width": 1 } });
    map.addSource("rings", { type: "geojson", data: EMPTY });
    map.addLayer({ id: "rings-fill", type: "fill", source: "rings", paint: { "fill-color": ACCENT, "fill-opacity": 0.04 } });
    map.addLayer({
      id: "rings-line",
      type: "line",
      source: "rings",
      paint: { "line-color": ACCENT, "line-width": 1.5, "line-dasharray": [3, 2] },
    });
    map.addSource("places", { type: "geojson", data: EMPTY });
    // Paint expressions are typed loosely by MapLibre; the shape is checked at runtime.
    map.addLayer({ id: "places", type: "circle", source: "places", paint: placePaint(null) as never });
    const subject = document.createElement("div");
    subject.className = "map-marker subject-marker";
    subject.setAttribute("role", "img");
    subject.setAttribute("aria-label", subjectLabel);
    const marker = new maplibregl.Marker({ element: subject }).setLngLat(center).addTo(map);
    const onClick = (event: maplibregl.MapLayerMouseEvent) => {
      const id = event.features?.[0]?.properties?.id as string | undefined;
      const place = id ? latest.current.allPlaces.get(id) : undefined;
      if (!place) return;
      setSelected(place);
      latest.current.onPlaceSelect?.(place.id);
    };
    const pointer = () => (map.getCanvas().style.cursor = "pointer");
    const reset = () => (map.getCanvas().style.cursor = "");
    map.on("click", "places", onClick);
    map.on("mouseenter", "places", pointer);
    map.on("mouseleave", "places", reset);
    return () => {
      marker.remove();
      map.off("click", "places", onClick);
      map.off("mouseenter", "places", pointer);
      map.off("mouseleave", "places", reset);
    };
    // Built once per map; data effects below keep it current.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [map, ready]);

  const ringKey = ringMiles.join("/") + center.join(",");
  useEffect(() => {
    if (!map || !ready) return;
    (map.getSource("rings") as GeoJSONSource | undefined)?.setData(ringFeatures(center, ringMiles));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [map, ready, ringKey]);
  useEffect(() => {
    if (!map || !ready) return;
    (map.getSource("places") as GeoJSONSource | undefined)?.setData(placeFeatures(places, anchors));
  }, [map, ready, places, anchors]);
  useEffect(() => {
    if (!map || !ready) return;
    (map.getSource("flood") as GeoJSONSource | undefined)?.setData(asCollection(flood));
  }, [map, ready, flood]);
  useEffect(() => {
    if (!map || !ready) return;
    for (const [property, value] of Object.entries(placePaint(category)))
      map.setPaintProperty("places", property as "circle-color", value as never);
  }, [map, ready, category]);
  useEffect(() => {
    if (!map || !ready) return;
    const show = (ids: string[], on: boolean) =>
      ids.forEach((id) => map.getLayer(id) && map.setLayoutProperty(id, "visibility", on ? "visible" : "none"));
    show(["rings-fill", "rings-line"], visible.rings);
    show(["places"], visible.places);
    show(["flood-fill", "flood-line"], visible.flood);
    if (!visible.places) setSelected(null);
  }, [map, ready, visible]);

  const hasPlaces = places.length + anchors.length > 0;
  const toggles: { key: keyof typeof visible; label: string; show: boolean }[] = [
    { key: "rings", label: "Radius rings", show: ringMiles.length > 0 },
    { key: "places", label: "Businesses", show: hasPlaces },
    { key: "flood", label: "Flood zone", show: !!flood },
  ];
  return (
    <div ref={setFrame}>
      <MapFrame
        containerRef={setEl}
        label={label}
        textAlternativeId={textAlternativeId}
        ready={ready}
        failed={failed}
        tileUrl={tileUrl}
        rings={ringMiles.length}
        className="analysis-map-frame"
        overlay={
          selected && (
            <MapPopup map={map} lngLat={[selected.lon, selected.lat]} label={selected.name} className="place-card">
              <div className="hover-card-head">
                <strong>{selected.name}</strong>
                <button type="button" className="icon-btn small" aria-label="Close" onClick={() => setSelected(null)}>
                  ×
                </button>
              </div>
              <small>
                {[selected.groupLabel ?? selected.group, distanceMi(selected.distance_mi), selected.closed ? "Possible closure · verify" : null]
                  .filter(Boolean)
                  .join(" · ")}
              </small>
              <small className="place-source">Source: {placesSource}</small>
            </MapPopup>
          )
        }
        below={
          toggles.some((t) => t.show) && (
            <fieldset className="map-layers">
              <legend className="sr-only">Map layers</legend>
              {toggles
                .filter((t) => t.show)
                .map((t) => (
                  <label key={t.key}>
                    <input
                      type="checkbox"
                      checked={visible[t.key]}
                      onChange={(event) => setVisible((v) => ({ ...v, [t.key]: event.target.checked }))}
                    />
                    {t.label}
                  </label>
                ))}
              {ringMiles.length > 0 && (
                <span className="map-layers-note">Radius rings {[...ringMiles].sort((a, b) => a - b).join(", ")} mi · display only</span>
              )}
            </fieldset>
          )
        }
      />
    </div>
  );
}
export type { MapLibreMap };
