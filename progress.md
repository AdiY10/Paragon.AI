# Implementation progress

## M0 — in progress
- Implementation plan adopted from reviewed commit 1fee667.
- Added resumable bounded Overture preservation CLI with per-extract hashes and source attribution.
- PRs #1–#3 merged; GitHub push and API permissions verified.
- Invite-only OIDC and membership APIs implemented and locally tested. Live deployment/provider callback and the product workflows remain incomplete.

Validation: 35 tests pass against real PostgreSQL 17/PostGIS 3.6 including the backend foundation. Kingston snapshots contain 2,863 September and 2,916 October records within 3 miles; hashes verified. October has 584 qualifying present businesses within 1 mile. The real Regal record changes from open to permanently_closed. Full portfolio capture completed with 68 successful extracts; P21 has no reference pin, and malformed seed rows P02/P26 were corrected with CSV quoting. Strict seed validation now runs before external lookups.

Backend scaffold now enforces private application/API access and rejects missing production secrets. The real PostGIS integration suite passes all 35 tests; SQLite passes 34 with one explicit spatial-test skip. Next: container/hosting manifests and source infrastructure. Admin role reassignment and access audit records are implemented. CI workflow is preserved on local branch ci/backend-verification; GitHub rejected its push because the current OAuth credential lacks workflow scope.

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
