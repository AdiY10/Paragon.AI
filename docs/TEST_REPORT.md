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
