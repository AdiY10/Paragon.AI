/** The one place MapLibre is imported (lazy-loaded with the map components). */
import * as maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import workerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url";

maplibregl.setWorkerUrl(workerUrl);

export { maplibregl };
export type { GeoJSONSource, LngLatBoundsLike, Map as MapLibreMap, Marker } from "maplibre-gl";
