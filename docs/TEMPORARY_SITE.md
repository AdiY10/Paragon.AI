# Temporary private OpenAI Site

Live URL: https://paragon-radar-workspace.amitsch5.chatgpt.site

The Sites plugin confirmed successful private publication and the Census update on 2026-11-18. The Site
is owner-only and uses ChatGPT sign-in; no separate Render account, OIDC client,
or paid hosting signup is required to use this temporary version. Open it with
the same ChatGPT account that owns the Site. Sharing has not been enabled.

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
  for the later move (export schema version 2).

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
`15f361441b7d5b6b164229c52253baa89cb45d9d` (Census update).

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
the live URL. Real owner sign-in/interaction must still be checked by opening the
private link; no interactive owner session was impersonated for production testing.

## Move later

1. Download and securely retain **Export workspace** before moving.
2. Deploy the canonical app and configure the destination identity provider.
3. Implement/test a transactional Django importer for the export schema, mapping
   Site user identity explicitly to the destination account. The importer does
   not exist yet; changing a URL alone will not move saved edits.
4. Validate counts, notes, source context, pin revisions, confirmation, and history
   against the export, then run destination login and source acceptance checks.
5. Keep this Site available until migration is verified.

No real business metrics or completed jobs were manufactured to bridge the runtime
limitations. No external paid resources were provisioned.
