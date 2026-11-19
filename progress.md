# Implementation progress

## Current priority: regular host, password access, and Site data migration

- PRs #1–#35 merged; password access and complete workspace migration are in main. Commits and PRs disclose Codex assistance.
- Canonical backend: invite-only auth; source registry/artifacts/snapshots/checks; durable jobs, schedules, recovery; versioned locations, public seed, Census previews/acceptance, manual pins, and address-change invalidation.
- Tenant domain now has explicit review, unknown anchor flags, version conflicts, idempotent creation, archive/history, and retirement on address changes. Seed/API/UI are next; no SEC mappings are guessed.
- Validation: 217 tests pass against PostgreSQL 17/PostGIS 3.6. Latest published Site has 15 frontend/adapter tests plus real Workers/D1/browser verification. Production backend build/static/private-route smoke and real Census reference flows passed in prior increments.
- Preserved source data: 70 actual Overture extracts across 35 reference pins; original retrieval dates, checksums, attribution, and the real Regal status change remain retained. P21 was initially unplaced; explicit Census ambiguity review is now available.

## Temporary Site

https://paragon-radar-workspace.amitsch5.chatgpt.site

The user changed its audience to public. The application still requires ChatGPT sign-in and isolates each visitor's records. It supports persistent portfolio/notes/pins, source-backed Census suggestions and source checks, responsive maps, and schema-3 migration export with explicit location links. Full trade-area analysis, scheduled ingestion, weekly signals, screening/comparison, and tenant UI remain incomplete. Preserve the public audience on subsequent publication.

## Next

Adi added a higher-priority regular-host/password migration task in AGENT_HANDOFF §0. Password access, workspace migration, and regular-host startup pass 253 PostGIS tests; password browser smoke and the actual 36-record private migration smoke pass. The production startup also passes an isolated PostGIS import/login/secure-cookie/restart/private-artifact smoke. Hosting access/budget and production cutover remain. The tenant seed/API work is preserved in Git stash on feat/tenant-seed-and-api. Resume it after the access priority.

Later, import only the actual dated tenant listing claims with qualifications; add private roster APIs and a working review UI; publish the corresponding Site adapter. Then implement versioned geography and the real profile data slice. No full Release 1 acceptance is claimed.

BLOCKER: Hosting credentials and approved resource budget for the full Django/PostGIS backend are not available.
Impact: Full-backend deployment, source workers, and final production acceptance cannot run yet. The limited temporary Site is available.
Minimum action needed: Owner connects Render with repository access and approves the prepared initial host budget of $14.55/month before tax/usage overages (docs/DEPLOYMENT.md). Future workers/backups require a separate quote.
Workaround in place: Local implementation and real public-source preservation continue.


BLOCKER: GitHub OAuth credential lacks workflow scope.
Impact: Cannot publish the tested CI workflow or run hosted verification.
Minimum action needed: Credential owner reauthorizes the existing GitHub OAuth access with workflow scope.
Workaround in place: CI branch retained locally; the same checks run locally before PR merges.

BLOCKER: OIDC deployment credentials are not configured.
Impact: The future Django deployment's live OIDC callback and final production AC-01/AC-02 remain unverified. The temporary Site uses built-in ChatGPT authentication.
Minimum action needed: Deployment owner supplies registered OIDC client/secret and issuer through the secret store.
Workaround in place: Mature provider integration and 29 offline tests, including verification, persistence, revocation, and CSRF.
