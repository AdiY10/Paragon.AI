import { useEffect, useRef, useState } from "react";
import { Crosshair } from "lucide-react";
import { Button } from "../ui/Button";
import { MapFrame } from "./MapFrame";
import { MapPopup } from "./MapPopup";
import { maplibregl, type Marker } from "./maplibre";
import { useMapLibre } from "./useMapLibre";
import { US_CENTER, US_ZOOM } from "./baseStyle";

export interface PickPoint {
  lat: number;
  lon: number;
}
const fmt = (p: PickPoint) => `${p.lat.toFixed(5)}, ${p.lon.toFixed(5)}`;

/**
 * Click anywhere to drop a draggable draft pin with "Analyze this point" / "Cancel". Keyboard path:
 * "Use map center". Default view = the portfolio's bounds, else the continental US.
 */
export function PickMap({
  initialBounds = null,
  draft,
  onPick,
  onConfirm,
  confirmLabel = "Analyze this point",
  busy = false,
  label = "Map: click a point to analyze it",
}: {
  initialBounds?: [[number, number], [number, number]] | null;
  draft: PickPoint | null;
  /** A new draft point, or null to cancel. */
  onPick: (point: PickPoint | null) => void;
  onConfirm: (point: PickPoint) => void;
  confirmLabel?: string;
  busy?: boolean;
  label?: string;
}) {
  const [el, setEl] = useState<HTMLDivElement | null>(null);
  const { map, ready, failed, tileUrl } = useMapLibre(el, {
    bounds: initialBounds,
    center: US_CENTER,
    zoom: US_ZOOM,
    padding: 48,
  });
  const marker = useRef<Marker | null>(null);
  const focusConfirm = useRef(false);
  const latest = useRef(onPick);
  latest.current = onPick;

  useEffect(() => {
    if (!map) return;
    const onClick = (event: maplibregl.MapMouseEvent) => latest.current({ lat: event.lngLat.lat, lon: event.lngLat.lng });
    map.on("click", onClick);
    map.getCanvas().style.cursor = "crosshair";
    return () => {
      map.off("click", onClick);
    };
  }, [map]);

  useEffect(() => {
    if (!map) return;
    if (!draft) {
      marker.current?.remove();
      marker.current = null;
      return;
    }
    if (!marker.current) {
      const pin = document.createElement("div");
      pin.className = "map-marker draft-marker";
      pin.setAttribute("role", "img");
      pin.setAttribute("aria-label", "Selected point");
      marker.current = new maplibregl.Marker({ element: pin, draggable: true }).setLngLat([draft.lon, draft.lat]).addTo(map);
      marker.current.on("dragend", () => {
        const p = marker.current!.getLngLat();
        latest.current({ lat: p.lat, lon: p.lng });
      });
    } else marker.current.setLngLat([draft.lon, draft.lat]);
  }, [map, draft]);
  useEffect(
    () => () => {
      marker.current?.remove();
      marker.current = null;
    },
    [map],
  );

  // The popup mounts once it knows the point's screen position; focus it then (keyboard path only).
  const confirmMounted = (node: HTMLButtonElement | null) => {
    if (node && focusConfirm.current) {
      focusConfirm.current = false;
      node.focus();
    }
  };

  return (
    <MapFrame
      containerRef={setEl}
      label={label}
      ready={ready}
      failed={failed}
      tileUrl={tileUrl}
      className="pick-map-frame"
      overlay={
        draft && (
          <MapPopup map={map} lngLat={[draft.lon, draft.lat]} label="Selected point" className="pick-card">
            <small className="pick-coords">{fmt(draft)}</small>
            <div className="pick-actions">
              <Button ref={confirmMounted} size="sm" disabled={busy} onClick={() => onConfirm(draft)}>
                {busy ? "Starting…" : confirmLabel}
              </Button>
              <Button variant="secondary" size="sm" onClick={() => onPick(null)}>
                Cancel
              </Button>
            </div>
          </MapPopup>
        )
      }
      below={
        <div className="pick-toolbar">
          <Button
            variant="secondary"
            size="sm"
            disabled={!map}
            onClick={() => {
              if (!map) return;
              const c = map.getCenter();
              focusConfirm.current = true;
              onPick({ lat: c.lat, lon: c.lng });
            }}
          >
            <Crosshair size={14} aria-hidden="true" /> Use map center
          </Button>
          <span className="pick-hint" aria-live="polite">
            {draft ? `Selected ${fmt(draft)}. Drag the pin to adjust.` : "Click the map or use the map center to choose a point."}
          </span>
        </div>
      }
    />
  );
}
