# Engineering decisions

## 2026-11-17 — implementation baseline
Follow docs/IMPLEMENTATION_PLAN.md, subject to AGENT_HANDOFF.md and the original acceptance criteria. Preserve public Overture history before interface development. Store large source captures outside Git, with record-level attribution and checksums. Seed coordinates remain explicitly unconfirmed public references. A missing seed pin is reported, never guessed.

Use focused PRs with clear validation and honest AI authorship. The requested 115-PR target does not justify empty or duplicate changes.

## Location identity and revision storage
Use finite latitude/longitude doubles as canonical pins and immutable numbered
revisions. PostGIS reference assets will supply indexed spatial queries; a separate
point column on the small location table is unnecessary. Keep optimistic edit version
separate from analysis generation so descriptive edits do not invalidate computations.
Seed-reference pins remain explicitly unconfirmed until a lookup or user confirmation.

## D-022 — Authenticated React application and visible implementation gaps

Serve a Vite-built React/TypeScript UI from Django, using the established private
APIs, masked CSRF token, and no-cache application HTML. WhiteNoise serves only
generic collected assets. System fonts avoid external font requests. The first
UI increment provides real record management and source transparency; unavailable
signal/screening/comparison pipelines remain explicit. Browser QA runs against an
ephemeral database containing the real public seed, with a test-only account.
Visual review and automated WCAG checks cover 375, 768, and 1280 pixels. The hosting
runtime suggested by the Sites skill does not support this Python/PostGIS worker
architecture, so deployment stays with the repository's documented topology.

## D-023 — Local map worker and policy-compliant OSM raster basemap

Use lazy MapLibre GL JS with a self-contained Vite worker on our static origin and
OSM raster tiles for initial private-app usage. Keep attribution visible, normal
browser caching, and origin-only cross-origin Referer. Document IP/viewed-area
privacy and permit disabling external tiles through runtime configuration. Retain
an accessible list, explicit tile/WebGL failures, and unplaced records. Browser
rings are geodesic display geometry, not server metric aggregation boundaries.

## D-024 — Snapshot edit versions and explicit pin-preview persistence

Capture the property version when opening an edit or pin dialog, rather than
reading a potentially refreshed prop at submit time. A newer background record
must force a conflict instead of permitting a stale form to overwrite it. Manual
pin changes remain a local preview until explicit save and create an immutable
revision through the existing API. Pin verification resets on movement and stays
independent of ownership. Native coordinate inputs provide a keyboard alternative
to drag. Use Radix modal navigation on phones so hidden desktop links cannot take
focus and the menu traps/restores focus correctly.

## D-025 — User-authorized temporary private OpenAI Sites deployment

Publish a separate portable Worker/D1 adapter for the working portfolio UI using
Sites-owned ChatGPT authentication and owner-private access. Preserve canonical
Django/PostGIS and its full data pipeline. Keep actual seed/source evidence, user
namespacing, atomic version/audit writes, and durable edits. Explicitly disable
unimplemented refresh/analysis and provide a versioned export. Mirror adapter source
and document the future importer/identity mapping instead of claiming URL changes
alone migrate data. No external paid provisioning or separate OIDC client is needed
for this temporary workspace.

## D-026 — Preserve Census interpolation uncertainty and mixed geography vintages

Use server-side single-address Census JSON with bounded transport, refused redirects,
request-echo validation, and sanitized errors. This endpoint does not report the
batch Exact/Non_Exact flag, so add a distinct interpolated method rather than infer
accuracy. Preserve ambiguous alternatives and no-match outcomes. Current Connecticut
county/BG and returned decennial blocks have different county prefixes: retain each
vintage rather than forcing a false hierarchy. Captured the three real documented
reference addresses before writing the parser.
