# Verification report — implementation in progress

No production deployment exists yet; this is not Release 1 acceptance.

| Verification | Result |
|---|---|
| Offline suite, Python 3.13, SQLite | 139 passed, 6 explicit spatial/concurrency skips |
| Same suite, PostgreSQL 17 and PostGIS 3.6 | 145 passed, no skips |
| Django configuration / migration consistency | Passed |
| Overture monthly captures | 70 extracts / 35 seed pins; all SHA-256 hashes verified; all imported into local PostGIS/artifact store |
| Real capture import rerun | Published zero; reused all 70; no duplicate snapshots |
| Source health replay | 35 scopes and 70 original-time checks; dates not refreshed by replay |
| Real portfolio seed | 36 unconfirmed properties / 35 reference pins; rerun created zero; one immutable batch retained |
| Real lost-message recovery | One receipt deliberately removed; original job completed after actual grace period; one recovery event retained |
| Real scheduler dispatch | One catalog-sync occurrence completed via worker; timing/lineage retained; verification schedule disabled afterward |
| Real durable worker | 16 catalog definitions processed; one attempt; message acknowledged; graceful shutdown verified |
| Historical Regal closure | Real Sep→Oct record pair preserved in tests |
| GitHub Actions | Not run: workflow push rejected for missing OAuth workflow scope |
| Production Gunicorn on private local socket | Health 200; app 302; anonymous session/locations/sources/jobs/schedules APIs 403; sign-in 200; HSTS verified |
| Render manifest | Official JSON-schema validation passed |
| Docker image / Compose | Prepared; cannot run without daemon access |
| Live OIDC / HTTPS / production ACs | Pending owner credentials and deployment |

The real database suite creates a separate test database, applies all migrations,
and tests membership, role changes, revocation, CSRF, access audit records,
case-insensitive SQL uniqueness, and spherical spatial distance. It does not yet
verify concurrent role mutation, source pipeline computations, product workflows,
performance, or production reliability. Test fixtures never populate production.

P21 (Mt. Kisco) has no resolved seed pin and has no Overture capture. The 70 archived
extracts are currently in ignored local runtime storage; durable off-machine storage
is still required before claiming retention/recovery readiness.

## Private UI milestone (2026-11-18)

- Production frontend build passes TypeScript and Vite bundling.
- 152 tests pass against PostgreSQL/PostGIS; 146 pass with six intentional skips
  on isolated SQLite. New coverage checks private HTML, local manifest paths,
  missing-build behavior, CSRF enforcement, and absence of account data in HTML.
- Four frontend transport tests pass: CSRF/body-based search, complete pagination,
  cross-origin pagination rejection, and sanitized conflict errors.
- Chromium passes 375/768/1280 layouts with no horizontal overflow and no automated
  WCAG A/AA violations on the dashboard after contrast corrections. Real API
  editing, confirmation, provenance, filters, source catalog, search, and anonymous
  denial pass in a disposable database using the actual public seed.
- Local screenshots were visually inspected. This does not establish full manual
  WCAG 2.2 compliance or production acceptance. Interactive geography and remaining
  data workflows are pending; no deployed preview is claimed.
- Production-settings Gunicorn smoke also passes for the built JavaScript/CSS,
  sign-in page, health endpoint, anonymous application redirect, and API denials.

## Interactive maps (2026-11-18)

153 PostgreSQL/PostGIS tests and eight frontend tests pass, including private runtime
map configuration and independent distance checks for every display-ring vertex.
The production build includes the explicit MapLibre v6 worker; its initial missing
worker integration was caught in Chromium and corrected before submission. Actual
OSM raster tiles, 35 saved pins, and three property rings were visually inspected.
Browser coverage includes map loading, map/list filters, responsive widths, automated
A/AA rules, and tile-failure retention of pins. Remaining deployed performance and
full accessibility acceptance are documented in MAPS.md; no production claim is made.
The final map browser run also passes injected external-tile failure, preserves all
35 saved markers, and reports no automated A/AA violations on the portfolio map.
SQLite passes 147 tests with six explicit skips. Production Gunicorn serves every
built map JS/CSS chunk and worker, with anonymous data APIs still denied.

## Pin correction and safe editing (2026-11-18)

The production frontend build and eight frontend tests pass. Chromium exercises
actual marker dragging, coordinate entry, explicit pin verification, and a save
through the real private API in the disposable seed database. It verifies a second
immutable manual revision, incremented analysis generation, and separate pin and
ownership confirmation. Phone navigation traps focus, closes on Escape, and restores
focus to its trigger; hidden desktop navigation cannot take focus.

A concurrent API edit while the record dialog is open is followed by an actual
background query refresh. Saving the older form returns a conflict, retains the
newer server notes, and offers a reload action. This catches the stale-form overwrite
risk when the live location prop's version changes during editing. Backend code is
unchanged from the 153-test PostGIS baseline. Full production acceptance remains open.
The final browser run also verifies phone-width pin-dialog overflow and retains an
inspected 375-pixel screenshot. Coordinate inputs and Save pin remain usable.

## Temporary private OpenAI Site (2026-11-18)

Published through the Sites plugin with terminal `succeeded` status and live URL
https://paragon-radar-workspace.amitsch5.chatgpt.site. Owner-private access was read
and preserved. Eight frontend tests and the production Worker build pass. Actual
local D1 SQL/Workers tests verify identity rejection, same-origin mutations, atomic
competing updates, audit consistency, and separate user namespaces. Chromium verifies
three responsive widths, A/AA rules, real map loading, persisted notes after reload,
manual pin revisions, and schema-versioned export. The test identity gateway is local
only and absent from the deployed artifact. Real owner interaction with the private
published URL is not impersonated or claimed. Full data-source/Release 1 acceptance
remains open; see TEMPORARY_SITE.md.

## Census adapter (2026-11-18)

Thirty adapter tests pass against the actual Norwalk match, Mount Kisco ambiguity,
and Kingston no-match responses, with SHA-256 manifests. Boundary tests reject
nonfinite/boolean/string coordinates, invalid GEOIDs, wrong response echoes,
oversized payloads, HTML, malformed JSON, and address-bearing transport errors.
Live retrievals reproduce Norwalk at 41.12661107292, -73.388299045728 and preserve
current CT planning-region codes separately from 2020 block geography. This adapter
milestone does not claim persisted lookup acceptance or a live Site geocoding UI.

## Persisted geocoding (2026-11-18)

199 tests pass on real PostgreSQL/PostGIS, including private lookup/accept APIs,
immutable source evidence, no pin mutation during lookup, explicit ambiguity choice,
no-match rejection, stale/expired/other-user/cross-record protection, unchanged cache
age/check history, repeated identical-response checks, and competing idempotent accepts.
SQLite passes 192 with seven explicit spatial/concurrency skips. PostgreSQL tests
caught and corrected nullable-join locking and concurrent revision snapshot issues.
The live isolated smoke retrieved the actual Staples Plaza address, persisted its
artifact, reused the cache without a second source check, and created one unconfirmed
Census pin revision. No configured portfolio database or real account was modified.

## Census review UI (2026-11-18)

TypeScript/Vite build and eight frontend transport/geography tests pass. Chromium
uses actual Census responses for public P03/P21/P20 in the disposable database.
Checks verify the one-match review, two unselected ambiguous choices with disabled
acceptance, unchanged saved pin on no match, persisted accepted source references,
and no auto-confirmed ownership/building. A 375-pixel dialog screenshot was inspected;
mobile overflow and automated A/AA rules pass. Property/search secondary-text contrast
was corrected after this broader dialog scan exposed it. Previous record/pin edits,
concurrent conflict, focus, maps, source cards, and failed-tile retention still pass.

## Private Site Census publication (2026-11-18)

Sites confirmed terminal `succeeded` publication at the existing owner-private URL
for source 15f361441b7d5b6b164229c52253baa89cb45d9d. Live database inspection confirms
additive geocode_lookups/source_checks alongside existing records/revisions/audits.
The original migration/snapshot files were unchanged. Fifteen Site frontend/adapter
tests and the production Worker build pass. Local actual Workers/D1 plus Chromium
verify live Census matched/ambiguous/no-match results, explicit choice and acceptance,
unchanged pins on no match, source hash/context and unverified status, no fake cache
re-checks, idempotent replay, rejected source spoofing and other-user acceptance,
real source health, and schema-2 export of raw lookup evidence. Existing persistence,
private APIs, responsive A/AA checks, and map loading pass. Real production owner
interaction is not impersonated or claimed; full Release 1 analysis remains pending.
