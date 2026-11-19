# Test report: Release 1 (batches A–D)

**Date:** 2026-11-19 · **Branch:** `main` after PRs #43–#50 · **Environment:** local preview (SQLite, Gunicorn, django-q worker and scheduler under `infra/start_all.py`) with **real data for all 35 pinned public-seed properties**, plus one real screened address.

## Automated suites

| Suite | Result |
|---|---|
| Backend (`uv run python -m pytest -q`) | **345 passed**, 9 skipped (PostGIS-only tests skip on SQLite) |
| Frontend (`npm test --prefix frontend`) | **21 passed** |
| Accessibility (axe-core, WCAG 2.0/2.1/2.2 A and AA) on This Week, two property pages, Screen, Compare, Portfolio, Data Sources at 1024 px; This Week, property page, Screen, Compare, Portfolio at 375 px | **0 violations** after fixes (empty-state contrast, 24 px map markers and small action buttons) |
| Horizontal overflow at 375 px (the same pages) | **None** |
| PostgreSQL/PostGIS suite (`make test-postgis`) | **Not run here.** There is no PostgreSQL on this machine. Amit's agent ran it for earlier increments; the new migrations use only portable fields (UUID, JSON, Char, Date). Run before deploying. |

## Real-data verification (preview, 2026-11-19)
- **Coverage:** all 35 pinned seed properties computed for demographics plus five area sections. 174 of 175 sections are available. The one gap is honest: Waterbury Office has no federal traffic count within 250 m.
- **Baseline brief:**
  - **2 High:** Cypress Lake and Saugatuck Restaurant in FEMA zone AE.
  - **Watch items include:** possible Walgreens closure 0.2 mi from Locust Retail; 5 properties with an SFHA within 100 m; Western CT unemployment +1.0 pt (one grouped item covering 11 properties); Frederick County private jobs −3.1%; Ward County retail jobs −4.5%; significant 3-mile real-income declines at 3 properties.
  - **Counts:** 211 signals in total, 34 owned properties with at least one active signal, attention High 2, Watch 19, Clear 15.
- **New screen:** "7 Backus Avenue, Danbury, CT" geocoded, pinned and fully computed in **28 s** (demographics 1.6 s, area sections 26 s including an Overture capture). The summary shows real strengths (3-mile population +10.9%, better than 83%) and concerns (FEMA zone A at the pin; main-road traffic weaker than 85%).
- **Tenants:** 99 listing tenants imported as unconfirmed claims. Rite Aid at Southside is mapped to CIK 84129, and its 2023-10-16 Item 1.03 filing shows as a past event.
- **Background pipeline:** `infra/start_all.py` ran Gunicorn, the django-q worker and the scheduler together, and executed queued `compute_ring_demographics` and `compute_area_profile` jobs.

## Performance (preview, warm cache, 3 requests each)

| Endpoint | Time | Target (docs/06 §5) |
|---|---|---|
| Location, demographics, area | 3–4 ms | p95 < 1.5 s |
| Summary (percentiles over 35 properties) | 22 ms | < 1.5 s |
| Compare (4 locations) | 27 ms | < 2 s |
| Signals list, latest brief, portfolio list | 4–9 ms | < 1.5 s |
| New screen to full profile | 28 s | core < 20 s (demographics 1.6 s), full < 90 s |

## P0 acceptance criteria (docs/02 §9)

| AC | Status | Evidence |
|---|---|---|
| AC-01 Auth on everything | Pass | Anonymous API requests return 403 (tests across new endpoints; verified on preview) |
| AC-02 Invite and remove | Pass (Amit's agent) | `test_accounts`, `test_password_access` |
| AC-03 36 unconfirmed seed records | Pass | `test_portfolio_seed`; no Esri figures imported |
| AC-04 Geocode reference and fallback | Pass | `test_census`, screen tests (exact and ambiguous) |
| AC-05 Pin move recomputes | Pass | Stale-after-pin-move tests (demographics, area); signals resolve as "location corrected" |
| AC-06 Ring population reference | Pass | Norwalk 10,719 / 85,544 within ±10% of 11,500 / 84,000 |
| AC-07 Non-overlapping trends with significance | Pass | `test_ring_demographics` trend tests |
| AC-08 County economy and CT planning regions | Pass | Area tests (Ulster County; Western CT Planning Region) |
| AC-09 Kingston traffic | Pass | US 9W 22,422 (2025), 22,523 (2024) |
| AC-10 Businesses and Regal closure | Pass | Business tests; SIG-09 Watch on the real Sep → Oct diff |
| AC-11 Cypress Lake flood | Pass | Zone AE, SFHA, BFE 9 ft; SIG-11 High |
| AC-12 Portfolio percentiles | Pass | `test_insights` |
| AC-13 Evidence for values | Pass | Sources per section, evidence drawers, signal evidence |
| AC-14 Missing data never 0 | Pass | Suppression and NOT_COVERED tests; UI shows reasons |
| AC-15 Signal rules | Pass | `test_signals` (every rule; thresholds; lifecycle) |
| AC-16 Brief composition and empty state | Pass | `test_brief` |
| AC-17 Rite Aid past event; recent 1.03 → High | Pass | `test_tenants_sec` (real EDGAR: Rite Aid 2023; Leslie's 2026) |
| AC-18 Screen | Pass | Screen tests and the real Danbury screen |
| AC-19 Evidence summary | Pass | `test_insights` |
| AC-20 Compare | Pass | `test_screen_compare`, browser check |
| AC-21 Source status and failure injection | Pass | T1 health test (Failing, last good kept, stale flags) |
| AC-22 Job rerun | Pass (Amit's agent) | `test_job_api` |
| AC-23 Attribution | Pass | Overture, OSM and federal sources cited in sections and on Data Sources |
| AC-24 Portfolio attention and filters | Pass | Attention badges, filter and sort; API tests |
| AC-25 No unsourced numbers | Pass | `test_every_rendered_number_has_source_and_period` plus manual review |

## Not verified here
- A deployed environment (no host approved; see `docs/DELIVERY_STATUS.md`).
- The PostGIS test suite.
- Live SEC daily refresh (requires `SEC_USER_AGENT` with a real contact email; tests use real recorded EDGAR responses).
- Email digest (P1, not built).

---

# Earlier increments (Amit's agent; preserved verbatim)

## Verification report — implementation in progress

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

## Address-change invalidation (2026-11-18)

206 tests pass on real PostgreSQL/PostGIS. New checks cover address/city/state
invalidation, pin/ownership reset with immutable old confirmation preserved,
original source-address retention after repeated edits, one analysis increment for
combined address/ring changes, unchanged-address/notes preservation, and rollback
of invalid edits. Frontend production build checks the explicit user-edited-address
provenance label. Temporary-Site address editing remains disabled until its adapter
and UI gain the same safeguards.

## Tenant domain (2026-11-18)

217 tests pass on real PostgreSQL/PostGIS. New coverage verifies unconfirmed/unknown
creation, attributed immutable history, creation replay after edits, changed-payload
rejection, cautious brand normalization, explicit confirmation, rename invalidation,
archive/restore, duplicate conflicts, unsupported mapping/source fields, owned-only
mutations, address-change retirement/rollback, and competing idempotent creation.
This domain increment does not yet claim a published tenant UI or SEC coverage.

## Priority password access (2026-11-19)

230 PostgreSQL/PostGIS tests pass, including shared-database concurrent throttle
limits, explicit opt-in, unknown/wrong/revoked account denial, CSRF, secure redirect
validation, logout, secret-free output, role preservation, and password rotation
invalidating sessions. SQLite passes 221 with nine explicit concurrency/spatial skips.
The production frontend build passes. A real Chromium password login without any
ChatGPT session or force-login bypass reaches the actual 36-record disposable seed,
survives reload, logs out, and loses API access. This is local verification; regular
hosting is not yet provisioned and external-browser/HTTPS acceptance remains open.

## Regular-host preparation (2026-11-19)

253 backend tests pass on PostgreSQL 17/PostGIS 3.6. Render blueprint validation passes
the official schema. The private 36-property live snapshot imports and replays with
field/pin/date comparisons. The production entrypoint passes disposable PostGIS QA:
wrong password denies access, real password opens the portfolio, cookies are secure
and HttpOnly, APIs deny anonymous access, logout works, notes/sessions survive process
restart, and archived export bytes match their original SHA-256. No auth bypass is
used. The socket simulates a trusted HTTPS ingress; external TLS, real Render mounts,
Docker image execution, and final production cutover remain unverified.

## Site migration contract (2026-11-19)

The schema-3 export passes a disposable actual Worker/D1 test: anonymous denial,
36 real seed properties, a test-only note/manual pin, both audit events and pin
relationships, and other-owner isolation. The generated export then passes the
Django disposable-database migration smoke with 36 properties, 37 total revisions,
and two audits. All 15 Site tests and the production build pass. No production
workspace data was modified by these tests.
