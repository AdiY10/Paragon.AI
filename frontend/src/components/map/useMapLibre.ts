import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import type { Session } from "../../types";
import { baseStyle, US_CENTER, US_ZOOM } from "./baseStyle";
import { maplibregl, type LngLatBoundsLike, type MapLibreMap } from "./maplibre";

export interface MapOptions {
  /** Initial view only; later changes never rebuild the map. */
  bounds?: LngLatBoundsLike | null;
  center?: [number, number];
  zoom?: number;
  maxZoom?: number;
  cooperativeGestures?: boolean;
  /** Fit padding for `bounds`. */
  padding?: number;
}
export type MapFailure = "webgl" | "tiles" | null;

/** Tile URL from the session (null when the server disables external tiles). */
export function useTileUrl(): string | null {
  return useQueryClient().getQueryData<Session>(["session"])?.map.tile_url ?? null;
}

/**
 * Creates one MapLibre map per mount of `el` and removes it on unmount (StrictMode-safe: the
 * second effect run builds a fresh map after the first is removed). Callers update the map with
 * setData / setFilter / class toggles, never by rebuilding.
 */
export function useMapLibre(el: HTMLElement | null, options: MapOptions = {}) {
  const tileUrl = useTileUrl();
  const [map, setMap] = useState<MapLibreMap | null>(null);
  const [ready, setReady] = useState(false);
  const [failed, setFailed] = useState<MapFailure>(null);
  useEffect(() => {
    if (!el) return;
    let instance: MapLibreMap | null = null;
    let cancelled = false;
    setReady(false);
    setFailed(null);
    try {
      instance = new maplibregl.Map({
        container: el,
        style: baseStyle(tileUrl),
        center: options.center ?? US_CENTER,
        zoom: options.zoom ?? US_ZOOM,
        maxZoom: options.maxZoom ?? 18,
        attributionControl: false,
        renderWorldCopies: false,
        cooperativeGestures: options.cooperativeGestures ?? true,
        dragRotate: false,
        pitchWithRotate: false,
        touchPitch: false,
      });
      instance.touchZoomRotate.disableRotation();
      instance.keyboard.disableRotation();
      instance.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
      instance.addControl(new maplibregl.ScaleControl({ unit: "imperial" }), "bottom-left");
      if (options.bounds) instance.fitBounds(options.bounds, { padding: options.padding ?? 48, maxZoom: 12, duration: 0 });
      instance
        .getCanvas()
        .setAttribute("aria-label", "Interactive map. Arrow keys pan, plus and minus zoom.");
      // One missing tile is normal; only a basemap that never loads is worth a message.
      instance.on("error", () => {
        if (!cancelled && instance && !instance.loaded()) setFailed("tiles");
      });
      instance.on("load", () => {
        if (!cancelled) setReady(true);
      });
      setMap(instance);
    } catch {
      instance?.remove();
      instance = null;
      setFailed("webgl");
    }
    return () => {
      cancelled = true;
      instance?.remove();
      setMap(null);
      setReady(false);
    };
    // Built once per element and tile URL; view options are initial values only.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [el, tileUrl]);
  return { map, ready, failed, tileUrl };
}
