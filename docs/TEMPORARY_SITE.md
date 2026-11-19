# Current OpenAI Site

Live URL: https://paragon-radar-workspace.amitsch5.chatgpt.site

The owner changed the Site audience to **public**. ChatGPT sign-in remains required,
and every visitor has a separate workspace. Preserve that audience on publication.
On 2026-11-19 the user explicitly chose to stay on this Site without external
hosting. Continue development here; the earlier migration request is deferred.

## Available now

- Actual public portfolio: 36 unconfirmed records, 35 reference pins, original
  source periods/attribution. Public listing data is not verified current ownership.
- Responsive portfolio UI, real OSM maps/rings, filters, private POST search,
  record creation/editing, notes, ownership confirmation, manual pin verification,
  and source-backed Census address suggestions with explicit review/acceptance.
- Persistent D1 records, immutable stored manual pin revisions, atomic optimistic
  version checks, user-scoped storage, and attributed change history.
- Actual on-demand Census check history plus historical metadata for the other
  sources. No fresh checks are claimed for the unimplemented background adapters.
- **Export workspace** downloads a private, schema-versioned JSON containing saved
  records, pin revisions, audit history, raw Census responses/hashes, and lookup/check history
  for the later move (export schema version 3, with workspace identity and explicit location links).

The Site is a working limited workspace, not completed Release 1. PostGIS spatial
aggregation, scheduled source ingestion, tenant SEC checks, weekly signals, screening,
and metric comparisons remain unavailable. The canonical Django/PostGIS app remains
under development; its deployment prerequisites still apply when moving there.

## Source and ownership

`sites/temporary/` mirrors the portable temporary adapter, schema migrations, real
bootstrap data, React UI, and verification scripts. The canonical backend/frontend
remain in `backend/` and `frontend/`; do not replace them with this adapter. The
hosted checkout is `/data/tml/code/as/vlm/paragon-radar-site`; its source was pushed
through the Sites helper and published at commit
`e947755079faa91b1afc0d28353161a3f4958ec9` (schema-3 migration export).

The tracked manifest preserves the existing Site identity. Reuse it for updates;
do not create a replacement Site. Source credentials remain session-only and are
not mirrored. The adapter uses dispatch-owned ChatGPT identity headers; its local
QA identity gateway is never included in the deployed Worker.

## Verification

Fifteen frontend/adapter tests, TypeScript/Vite production build, and local actual Workers/D1
SQL execution pass. Checks cover anonymous denial, same-origin mutation protection,
competing version updates, account isolation, 375/768/1280 overflow and automated
A/AA rules, actual map-worker/pin loading, persisted edits after reload, manual pin
revisions, complete export, live Census match/ambiguity/no-match, cache age/replay,
source-field spoof rejection, and cross-user acceptance denial. Native Sites publication returned `succeeded` and
the live URL. Real visitor sign-in/interaction must still be checked by opening the
live link; no interactive owner session was impersonated for production testing.

## Deferred migration reference

The Django transactional importer is implemented and tested. It validates complete
portfolios, retains original private export bytes/checksums, imports notes/pins/audits,
revalidates Census evidence, and refuses conflicting destination edits. Imported
actor metadata grants no account access. Follow [WORKSPACE_MIGRATION.md](WORKSPACE_MIGRATION.md).

The 2026-11-19 private capture has 36 unchanged properties and no audit/lookup history.
A schema-3 Worker/D1 test creates a note/manual pin and exports their history, checks
owner isolation, then imports that actual export through the Django smoke check.
This verifies the migration contract without modifying production business data.

The regular-host blueprint and named password login are retained for a possible
later move. That work is deferred by user choice, not a prerequisite for Site feature
development. Keep this Site active and preserve existing records. A future move
would require separate authorization and completed production cutover checks.

No business metrics or completed jobs were manufactured. No external paid resources
were provisioned. Export files remain private and are never committed.
