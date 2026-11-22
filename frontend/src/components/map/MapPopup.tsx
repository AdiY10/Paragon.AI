import { useEffect, useState, type ReactNode } from "react";
import type { MapLibreMap } from "./maplibre";

/** Follows a map coordinate in screen space; null while the point is off-screen. */
export function useScreenPoint(map: MapLibreMap | null, lngLat: [number, number] | null) {
  const [point, setPoint] = useState<{ x: number; y: number } | null>(null);
  const lon = lngLat?.[0],
    lat = lngLat?.[1];
  useEffect(() => {
    if (!map || lon === undefined || lat === undefined) {
      setPoint(null);
      return;
    }
    const update = () => {
      const p = map.project([lon, lat]);
      const canvas = map.getCanvas();
      const visible = p.x >= 0 && p.y >= 0 && p.x <= canvas.clientWidth && p.y <= canvas.clientHeight;
      setPoint(visible ? { x: p.x, y: p.y } : null);
    };
    update();
    map.on("move", update);
    map.on("resize", update);
    return () => {
      map.off("move", update);
      map.off("resize", update);
    };
  }, [map, lon, lat]);
  return point;
}

/**
 * A card anchored to a coordinate, rendered by React over the map (no MapLibre Popup DOM), so its
 * buttons and links are ordinary focusable elements. Flips below the point near the top edge.
 */
export function MapPopup({
  map,
  lngLat,
  label,
  className = "",
  onPointerEnter,
  onPointerLeave,
  children,
}: {
  map: MapLibreMap | null;
  lngLat: [number, number] | null;
  label: string;
  className?: string;
  onPointerEnter?: () => void;
  onPointerLeave?: () => void;
  children: ReactNode;
}) {
  const point = useScreenPoint(map, lngLat);
  if (!point) return null;
  const below = point.y < 170;
  const width = map?.getCanvas().clientWidth ?? 0;
  // Keep the card inside the map horizontally (card is ≤260 px wide).
  const shift = Math.max(Math.min(0, width - 8 - (point.x + 130)), Math.max(0, 8 - (point.x - 130)));
  return (
    <div
      className={`map-popup-card ${below ? "below" : "above"} ${className}`.trim()}
      role="group"
      aria-label={label}
      style={{ left: point.x, top: point.y, ["--shift" as string]: `${shift}px` }}
      onPointerEnter={onPointerEnter}
      onPointerLeave={onPointerLeave}
    >
      {children}
    </div>
  );
}
