# Implementation progress

## M0 — in progress
- Implementation plan adopted from reviewed commit 1fee667.
- Added resumable bounded Overture preservation CLI with per-extract hashes and source attribution.
- PRs #1–#21 merged; GitHub push and API permissions verified.
- Invite-only OIDC and membership APIs implemented and locally tested. Live deployment/provider callback and the product workflows remain incomplete.

Validation: 152 tests pass against real PostgreSQL 17/PostGIS 3.6 including the backend foundation. Kingston snapshots contain 2,863 September and 2,916 October records within 3 miles; hashes verified. October has 584 qualifying present businesses within 1 mile. The real Regal record changes from open to permanently_closed. Full portfolio capture completed with 70 successful extracts; P21 has no reference pin, and malformed seed rows P02/P26 were corrected with CSV quoting. Strict seed validation now runs before external lookups.

Backend scaffold now enforces private application/API access and rejects missing production secrets. The real PostGIS integration suite passes all 152 tests; SQLite passes 146 with explicit spatial/concurrency skips. Production Gunicorn smoke passes with real migrations and strict settings; Render manifest passes official schema validation. Docker/Compose build is unverified because the daemon is inaccessible. Versioned source catalog and private source-metadata API are implemented. Private content-addressed artifact storage now passes interruption, corruption, limit, deduplication, and concurrent-publication checks. Immutable snapshot publication now persists verified artifacts before database records, rejects incomplete/failed batches and conflicting provenance, and retains source revisions. All 70 actual captures were validated and published into the local PostGIS snapshot registry and private artifact store; rerun published zero and reused all 70. Original retrieval time, pin context, and source attribution are retained. Scoped source health and immutable checks now preserve last-good snapshots and reconcile historical replay. The 70 real archives produced 35 scoped health records and 70 original-time checks. Durable job submission and execution are implemented. A real ORM-queued worker synchronized 16 catalog entries in one attempt, acknowledged the message, and shut down gracefully. Administrator run logs and idempotent submission/rerun APIs are implemented with role checks and retained lineage. Eastern wall-clock recurrence and required schedule definitions now pass DST, monthly-boundary, and missed-run coalescing tests. Persistent schedule dispatch now passes competing-leader, rollback, and replay tests. A real local catalog occurrence completed through the worker and was acknowledged; the verification schedule was then disabled. Missing source handlers remain explicitly disabled. Interrupted-job recovery now passes concurrent sweep, prefetch, lease, backoff, and rollback checks. Real missing-message fault injection recovered one original job through the worker. Location status/provenance, immutable pin revisions, optimistic edits, analysis generations, and confirmation/audit services now pass real database tests. The real 36-property seed imported as Owned/Unconfirmed with 35 reference pins; rerun retained all rows and one immutable batch. Concurrent import and edit-preservation tests pass. Private location create/read/edit/confirm/archive/pin/history/search APIs now pass validation and production anonymous-route checks. Address search is in POST bodies. No profile values are synthesized; geocoding and calculations remain pending. A responsive authenticated UI now builds and passes browser checks for real record management, source coverage, and review counts; see docs/USER_INTERFACE.md. Metrics and weekly brief are visibly unavailable. Next: interactive geography, geocoding, and tenant management. Admin role reassignment and access audit records are implemented. CI workflow is preserved on local branch ci/backend-verification; GitHub rejected its push because the current OAuth credential lacks workflow scope.

BLOCKER: Hosting credentials and approved resource budget are not available.
Impact: Live M0 deployment and production verification cannot run yet.
Minimum action needed: Owner supplies deployment access and approves the concrete resource quote once prepared.
Workaround in place: Local implementation and real public-source preservation continue.


BLOCKER: GitHub OAuth credential lacks workflow scope.
Impact: Cannot publish the tested CI workflow or run hosted verification.
Minimum action needed: Credential owner reauthorizes the existing GitHub OAuth access with workflow scope.
Workaround in place: CI branch retained locally; the same checks run locally before PR merges.

BLOCKER: OIDC deployment credentials are not configured.
Impact: Live authentication callback and production AC-01/AC-02 remain unverified.
Minimum action needed: Deployment owner supplies registered OIDC client/secret and issuer through the secret store.
Workaround in place: Mature provider integration and 29 offline tests, including verification, persistence, revocation, and CSRF.
