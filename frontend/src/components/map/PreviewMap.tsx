import { useEffect, useRef, useState } from "react";
import { MapFrame } from "./MapFrame";
import { maplibregl, type Marker } from "./maplibre";
import { useMapLibre } from "./useMapLibre";

/**
 * One pin for review dialogs (pin editor, Census suggestions). Coordinate changes move the pin and
 * re-centre the map; a draggable pin reports where it was dropped. Typed coordinates next to the
 * map are the dragging alternative.
 */
export function PreviewMap({
  lat,
  lon,
  draggable = false,
  onMove,
  label = "Pin preview map",
  zoom = 16,
}: {
  lat: number;
  lon: number;
  draggable?: boolean;
  onMove?: (lat: number, lon: number) => void;
  label?: string;
  zoom?: number;
}) {
  const [el, setEl] = useState<HTMLDivElement | null>(null);
  const { map, ready, failed, tileUrl } = useMapLibre(el, { center: [lon, lat], zoom, cooperativeGestures: true });
  const marker = useRef<Marker | null>(null);
  const dragged = useRef(false);
  const latest = useRef(onMove);
  latest.current = onMove;

  useEffect(() => {
    if (!map) return;
    const pin = document.createElement("div");
    pin.className = "map-marker preview-marker";
    pin.setAttribute("role", "img");
    pin.setAttribute("aria-label", draggable ? "Pin preview (draggable)" : "Pin preview");
    const m = new maplibregl.Marker({ element: pin, draggable }).setLngLat([lon, lat]).addTo(map);
    m.on("dragend", () => {
      const p = m.getLngLat();
      dragged.current = true;
      latest.current?.(p.lat, p.lng);
    });
    marker.current = m;
    return () => {
      m.remove();
      marker.current = null;
    };
    // Created once per map; the effect below follows coordinate changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [map, draggable]);

  useEffect(() => {
    if (!map || !marker.current) return;
    marker.current.setLngLat([lon, lat]);
    // A drop already put the pin where the user wants it; typed or chosen coordinates re-centre.
    if (dragged.current) dragged.current = false;
    else map.easeTo({ center: [lon, lat], duration: 300 });
  }, [map, lat, lon]);

  return (
    <MapFrame
      containerRef={setEl}
      label={label}
      ready={ready}
      failed={failed}
      tileUrl={tileUrl}
      pins={1}
      className="preview-map-frame"
    />
  );
}
