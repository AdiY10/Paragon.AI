import type { StyleSpecification } from "maplibre-gl";

export const OSM_ATTRIBUTION =
  '© <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">OpenStreetMap</a> contributors';
export const BASE_BACKGROUND = "#F1F5F9";
/** Continental US view when nothing is pinned. */
export const US_CENTER: [number, number] = [-98.58, 39.83];
export const US_ZOOM = 3.2;

/**
 * Greyed OSM raster on slate. No glyphs and no sprite: the CSP allows only 'self' and
 * tile.openstreetmap.org, so text and icons are HTML (pins) or absent (circle/fill/line layers).
 */
export function baseStyle(tileUrl: string | null | undefined): StyleSpecification {
  return {
    version: 8,
    sources: tileUrl
      ? {
          basemap: {
            type: "raster",
            tiles: [tileUrl],
            tileSize: 256,
            maxzoom: 19,
            attribution: OSM_ATTRIBUTION,
          },
        }
      : {},
    layers: [
      { id: "background", type: "background", paint: { "background-color": BASE_BACKGROUND } },
      ...(tileUrl
        ? [
            {
              id: "basemap",
              type: "raster" as const,
              source: "basemap",
              paint: { "raster-saturation": -0.9, "raster-opacity": 0.95, "raster-contrast": -0.05 },
            },
          ]
        : []),
    ],
  };
}
