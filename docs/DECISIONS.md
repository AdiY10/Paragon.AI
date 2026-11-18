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

## D-027 — Explicit source-backed geocode acceptance and independent check time

Publish a bounded response to private artifact storage, then create an immutable
requester-scoped preview. Pin mutation is a separate explicit version-checked action
using only the stored candidate index. Keep accepted pins unconfirmed. Cache by saved
address for 30 days, without fabricating re-checks. Identical re-fetched bytes may
reuse a content snapshot but must preserve a later actual check time/expiry in a new
preview. Lock the location before reading its current revision in a separate query;
a nullable outer join can fail or expose a stale snapshot under competing accepts.

## D-028 — Review address suggestions before source-backed pin changes

Use a separate disclosed lookup action, explicit candidate selection, and explicit
acceptance. Never preselect ambiguous alternatives or overwrite on lookup. Keep
building/ownership verification separate. Show a true unsaved map and source check/
capture dates, with exactness and geography-vintage details available for audit.
Preview markers do not link to nonexistent records. Extend browser verification
with live public-reference requests and phone-width accessibility checks.

## D-029 — Publish on-demand Census on the existing private Site

Adapt the same reviewed geocoding contract to HTTP-only Workers and D1, keeping
owner namespaces, explicit acceptance, immutable source response hashes, actual
check history, cache age, source-field rejection, and idempotent acceptance replay.
Append schema-only lookup/check tables; do not change existing record/pin tables or
reseed user edits. Export schema 2 adds raw response and check evidence for later
migration. Keep ChatGPT authentication/audience unchanged. Only on-demand Census
checks are live; other background sources remain explicitly unimplemented.

## D-030 — Address/locality changes invalidate location-specific confirmation

Treat changes to address, city, or state as a new location context. In one locked
transaction, create an unplaced revision, clear ownership/building confirmation,
advance analysis once, preserve the original source address and immutable pin history,
and audit the reason. Ring and address changes together advance one generation.
Unchanged values and notes-only edits preserve their existing pin. Mark edited
addresses explicitly in provenance rather than attributing them to the old listing.
