# Verification report — implementation in progress

No production deployment exists yet; this is not Release 1 acceptance.

| Verification | Result |
|---|---|
| Offline suite, Python 3.13, SQLite | 59 passed, 1 spatial test explicitly skipped |
| Same suite, PostgreSQL 17 and PostGIS 3.6 | 60 passed, no skips |
| Django configuration / migration consistency | Passed |
| Overture monthly captures | 70 extracts / 35 seed pins; all SHA-256 hashes verified; all imported into local PostGIS/artifact store |
| Real capture import rerun | Published zero; reused all 70; no duplicate snapshots |
| Historical Regal closure | Real Sep→Oct record pair preserved in tests |
| GitHub Actions | Not run: workflow push rejected for missing OAuth workflow scope |
| Production Gunicorn on private local socket | Health 200; app 302; anonymous API 403; sign-in 200; HSTS verified |
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
