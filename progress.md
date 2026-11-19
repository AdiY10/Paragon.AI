# Implementation progress

## Current priority: continue on the existing OpenAI Site

- PRs #1–#35 merged; password access and complete workspace migration are in main. Commits and PRs disclose Codex assistance.
- Canonical backend: invite-only auth; source registry/artifacts/snapshots/checks; durable jobs, schedules, recovery; versioned locations, public seed, Census previews/acceptance, manual pins, and address-change invalidation.
- Tenant domain now has explicit review, unknown anchor flags, version conflicts, idempotent creation, archive/history, and retirement on address changes. Seed/API/UI are next; no SEC mappings are guessed.
- Validation: 253 tests pass against PostgreSQL 17/PostGIS 3.6. Latest published Site has 15 frontend/adapter tests plus real Workers/D1/browser verification. Production backend build/static/private-route smoke and real Census reference flows passed in prior increments.
- Preserved source data: 70 actual Overture extracts across 35 reference pins; original retrieval dates, checksums, attribution, and the real Regal status change remain retained. P21 was initially unplaced; explicit Census ambiguity review is now available.

## Temporary Site

https://paragon-radar-workspace.amitsch5.chatgpt.site

The user changed its audience to public. The application still requires ChatGPT sign-in and isolates each visitor's records. It supports persistent portfolio/notes/pins, source-backed Census suggestions and source checks, responsive maps, and schema-3 migration export with explicit location links. Full trade-area analysis, scheduled ingestion, weekly signals, screening/comparison, and tenant UI remain incomplete. Preserve the public audience on subsequent publication.

## Next

The user explicitly declined external hosting on 2026-11-19: stay on the current
Site. This supersedes the earlier migration priority. No paid resources were
provisioned; do not request a Render connection or budget to continue Site work.
The tested backend/password/bootstrap/importer remain available for a later move.

Resume tenant roster work: actual dated listing claims with qualifications, private
roster APIs, explicit review UI, and the corresponding persistent Site adapter.
The unfinished canonical seed/API work remains preserved in Git stash on
feat/tenant-seed-and-api. Then implement the versioned geography/profile data slice
using supported Site capabilities. Publish verified increments to the existing URL.
No full Release 1 acceptance is claimed.

## Deferred external deployment

External hosting, Django workers, and live external OIDC are deferred by user choice.
They are not blockers to Site development. The Site retains ChatGPT sign-in and
per-user isolation; the prepared password login is not deployed there. Runtime
limitations still need explicit implementation and verification before acceptance.

BLOCKER: GitHub OAuth credential lacks workflow scope.
Impact: Cannot publish the tested CI workflow or run hosted verification.
Minimum action needed: Credential owner reauthorizes the existing GitHub OAuth access with workflow scope.
Workaround in place: CI branch retained locally; the same checks run locally before PR merges.
