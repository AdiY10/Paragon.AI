import type { ReactNode, Ref } from "react";
import type { MapFailure } from "./useMapLibre";

/**
 * The frame every map shares: a "Skip map" link, a labelled region that points to its text
 * alternative, status messages for missing WebGL / tiles / disabled basemap, OSM attribution and
 * a privacy line. `data-ready`, `data-pins` and `data-rings` are for the browser smoke test.
 */
export function MapFrame({
  containerRef,
  label,
  textAlternativeId,
  skipTargetId,
  ready,
  failed,
  tileUrl,
  pins,
  rings,
  className = "",
  overlay,
  below,
  height,
}: {
  containerRef: Ref<HTMLDivElement>;
  /** Region name, e.g. "Map of owned properties". */
  label: string;
  /** Id of the element (table, list) that holds the same items as text. */
  textAlternativeId?: string;
  /** Where "Skip map" moves focus; defaults to the text alternative. */
  skipTargetId?: string;
  ready: boolean;
  failed: MapFailure;
  tileUrl: string | null;
  pins?: number;
  rings?: number;
  className?: string;
  /** Absolutely positioned content over the map (hover card, popup). */
  overlay?: ReactNode;
  /** Content between the map and the attribution (legend, layer toggles). */
  below?: ReactNode;
  height?: string;
}) {
  const skipTo = skipTargetId ?? textAlternativeId;
  return (
    <div className={`map-frame ${className}`.trim()}>
      {skipTo && (
        <a
          className="skip-map"
          href={"#" + skipTo}
          onClick={(event) => {
            // The hash belongs to the router: move focus without changing it.
            event.preventDefault();
            const target = document.getElementById(skipTo);
            if (!target) return;
            if (!target.hasAttribute("tabindex")) target.setAttribute("tabindex", "-1");
            target.focus();
          }}
        >
          Skip map
        </a>
      )}
      <div className="map-stage" style={height ? { height } : undefined}>
        <div
          ref={containerRef}
          className="location-map"
          role="region"
          aria-label={label}
          aria-describedby={textAlternativeId}
          data-ready={ready ? "true" : undefined}
          data-pins={pins === undefined ? undefined : String(pins)}
          data-rings={rings === undefined ? undefined : String(rings)}
        />
        {overlay}
        {failed === "webgl" && (
          <p className="map-message" role="status">
            Map unavailable: this browser could not start WebGL. Everything on the map is also listed as text.
          </p>
        )}
      </div>
      {failed === "tiles" ? (
        <p className="map-status" role="status">
          Basemap tiles unavailable. Pins and rings still show saved coordinates; the list has every detail.
        </p>
      ) : !tileUrl ? (
        <p className="map-status">Basemap disabled. Pins and rings are drawn on a blank background.</p>
      ) : null}
      {below}
      <p className="map-credit">
        {tileUrl ? (
          <>
            Map tiles ©{" "}
            <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">
              OpenStreetMap
            </a>{" "}
            contributors. The tile server sees your IP address and the area you view, never property names or notes.
          </>
        ) : (
          "External map tiles are turned off."
        )}
      </p>
    </div>
  );
}
