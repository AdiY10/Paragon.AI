# Interactive location maps

Four map components share one frame (`src/components/map/`): a "Skip map" link, a labelled
region described by its text alternative (the properties table, the retail list), messages for
missing WebGL, failed tiles or a disabled basemap, OSM attribution and a privacy line.

- **PortfolioMap** (Properties): every owned property as an HTML `<button>` pin (High: red
  circle with "!", Watch: amber diamond with "!", Clear: slate dot; 24 px hit area), merged
  into cluster buttons within 40 px on screen ("4 properties (1 High): …. Zoom in"). Pins are
  created once; filters toggle visibility and re-fit the view; one hover card is reused.
- **AnalysisMap** (analysis pages): the pin, dashed radius rings (display only), nearby
  businesses as circles (selected category in accent, anchors larger, possible closures hollow
  red) and the flood polygon when available; layer checkboxes sit outside the map.
- **PickMap** (Analyze): a click drops a draggable draft pin with "Analyze this point";
  "Use map center" is the keyboard path.
- **PreviewMap** (pin editor, Census review): one pin; typed coordinates are the dragging
  alternative.

No map uses glyphs, sprites or symbol layers: the CSP allows only this origin and
tile.openstreetmap.org, so all text on maps is HTML. Pin confirmation is separate from
ownership. **Correct pin** opens an unsaved preview: drag the marker or enter coordinates,
then save explicitly; Cancel leaves the saved revision intact.

MapLibre GL JS is lazy-loaded only on screens that show a map. Its v6 module worker
is bundled using Vite's `?worker&url` integration, then served from the application's
own static origin. A successful marker overlay alone does not prove the worker or
basemap loaded: browser verification waits for `data-ready`, the pin count (`data-pins`) and
the three rings (`data-rings`).
See [MapLibre installation](https://maplibre.org/maplibre-gl-js/docs/).

## Basemap provider and privacy

Default provider: OpenStreetMap standard raster tiles at
`https://tile.openstreetmap.org/{z}/{x}/{y}.png`, with visible OpenStreetMap attribution
and a report-map-issue link. The basemap is contextual, not a source for property
ownership, businesses, hazard determinations, or computed metrics. Coverage is global;
updates follow OSM edits and tile rendering, without a fixed property-level period.
The provider offers best-effort availability rather than an SLA.

Use normal interactive browsing only: no tile bulk download, offline prefetch, or
cache bypass. Browser cache headers are retained. Cross-origin requests send only
the application's origin as Referer, satisfying the provider policy without exposing
property paths, search addresses, or hashes. The provider sees IP and tile coordinates
(viewed area), but property names, notes, and account information are not sent.
The app's Data Sources screen links this privacy explanation.

The runtime `MAP_TILE_URL` setting can point to an OSM-compatible raster service, or
be blank to disable external basemap requests. It is browser-visible: never insert
private credentials. Attribution is for OSM data; a provider requiring additional
attribution needs a reviewed configuration change. Recheck the
[OSMF tile policy](https://operations.osmfoundation.org/policies/tiles/) before scaling
or changing the delivery/caching topology. Source terms were reviewed 2026-11-18.
No paid account or API key was provisioned.

## Geometry and failures

Displayed rings use geodesic destinations on a sphere with mean Earth radius
6,371,008.8 m and exact mile conversion 1,609.344 m. They are 128-segment display
polygons. Tests independently check every vertex with the haversine distance at
Connecticut, Florida, and Alaska latitudes. These browser rings are **display only**;
metric weighting and spatial analysis must use the plan's versioned, server-side
PostGIS geography and source-specific methods. Rings do not imply data availability.

Failed tile requests show a warning while retaining coordinate overlays and the
list. A WebGL initialization failure explicitly offers the list. Blank basemap
configuration is labelled “coordinate overlay only.” No synthetic map replaces a
failed provider. Original coordinate attribution remains in property provenance.

## Verification and remaining checks

The isolated browser smoke verifies the actual public seed, map-worker loading,
35 markers, three property rings, map/list filtering, desktop/tablet/phone overflow,
automated A/AA rules, and an injected tile-network failure. Successful raster loading
and ring rendering were visually reviewed. The build reports a large lazy MapLibre
chunk (~300 KB gzip plus its worker); performance acceptance on deployed hardware
remains open. Production domain, provider callback, real user accessibility checks,
and all data-layer acceptance are separate from this local milestone.
