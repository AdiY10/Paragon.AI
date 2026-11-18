# Paragon Radar temporary private Site

This repository adapts the verified React interface from AdiY10/Paragon.AI commit
3becd634333db5a7ba89618fc2ee28d9856662f0 for OpenAI Sites. The canonical Python/Django/
PostGIS implementation remains intact in that GitHub repository.

Sites owns ChatGPT sign-in and owner-private access. The Worker additionally rejects
requests without the authenticated Site user headers. Records are namespaced by the
stable Site user ID, with persistent D1 storage and version-checked atomic writes.
Mutations require same-origin JSON requests; raw addresses never enter search URLs.
No OAuth client, password signup, paid hosting account, or external database is needed
for this temporary Site.

## Working features

The actual 36-property public seed (35 reference pins, ownership unconfirmed), maps,
source provenance and historical source checks, record creation/filtering/search,
notes and attributes, ownership confirmation, manual pin revisions/verification,
change history, responsive navigation, and workspace JSON export.

Source health is explicitly not checked on this Site. Historical data periods and
successful check dates are retained without claiming new retrievals. No mock metrics
or jobs exist. Census/geography calculations, scheduled ingestion, weekly signals,
SEC tenant checks, screening, and comparable metrics remain unavailable. D1 is not a
replacement for the planned PostGIS spatial pipeline or archived source storage.

## Build and verify

Node.js 22.13+:

```
npm ci
npm run build
npm test
CHROMIUM_PATH=/path/to/chromium node scripts/browser-qa.mjs
```

The build emits a self-contained ESM Worker and local JS/CSS/map-worker assets in
`dist/server/index.js`, with Sites metadata and schema-only Drizzle migrations in
`dist/.openai`. Seeds are real, unchanged public records kept outside migrations.
The D1 tables are never created/altered during request handling. The QA gateway
injects a test identity only in an ephemeral local Miniflare test; it is not part
of the deployment build. Source/schema, assets and tests remain portable.

## Moving later

Download **Export workspace** from the banner or Admin. The private JSON contains
schema_version, export time, all saved locations with source context/current pin,
all persisted manual pin revisions, and audit history. Initial public pin evidence
is embedded in each seeded record; the first manual move also retains its previous
revision. Keep the export private.

Deploy the canonical Django/PostGIS app on the eventual host, configure its chosen
identity provider, and import the exported records/revisions/history with ID mapping
and validation. A Django importer is not implemented yet: validate that migration
before changing the destination URL. Site-scoped user IDs differ from destination
auth identities and must be explicitly mapped; never treat an email alone as proof
of account ownership. Keep this Site available until the destination is verified.

This temporary Site is not full Release 1 acceptance. It is private to its owner;
sharing with more users requires an explicit access-policy change.

## Census address review update

Find address pin now performs on-demand Census lookup with explicit review and
acceptance, no automatic building/ownership confirmation, 30-day cached evidence,
and real per-location source-check history. Ambiguous results require selection;
no match leaves the saved pin intact. Nominatim remains disabled. The UI comes from
canonical commit 8eb9412c3dc2e573408b7bb26d397385b3a7393f.

Additive migration 0001 creates only geocode_lookups and source_checks; existing
record, audit, and pin tables remain unchanged. Export schema version 2 additionally
includes the private raw Census responses/hashes, lookup history, and source checks.
The destination importer must handle both earlier version 1 and version 2 exports.
Fifteen frontend/adapter tests and the actual local Workers/D1 browser workflow
verify real Census match, ambiguity, no match, cache age, acceptance replay,
provenance-field rejection, and cross-user denial. Production owner interaction is
not impersonated by those local tests.
