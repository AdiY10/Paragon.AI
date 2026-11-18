# Temporary Sites deployment and later migration

Canonical implementation: https://github.com/AdiY10/Paragon.AI
Base commit: 3becd634333db5a7ba89618fc2ee28d9856662f0.
The temporary Site has a separate source repository so its Worker adapter does not
replace or constrain Django/PostGIS. Its React source derives from the canonical UI.

The owner-private Site uses ChatGPT authentication. Stable Site user IDs namespace
D1 records; usernames/emails are displayed only. No secrets or bypass tokens exist
in client code. Source metadata is a dated snapshot, not a live ingestion service.

Before moving, download Export workspace and retain it securely. Validate the
schema-versioned JSON and create explicit destination identity mappings. Add/test
a Django importer for saved locations, current and historical revisions, and audits.
Use optimistic versions and transactional writes; preserve source periods and
confirmation status; do not run the public seed importer over user edits. Back up
both environments. Compare record/revision/audit counts and representative values,
then verify actual login, notes, pins, source evidence, and unavailable states at
the destination. Keep the temporary Site until those checks pass.

There is no automatic Django importer yet. Changing the URL alone will not transfer
D1 edits. The export action and source are available now so migration can be done
without redesigning the UI or losing the collected records.

Export version 2 adds geocode_lookups and source_checks. Verify each raw_response's
SHA-256 against its source.sha256 before publishing it into destination private
artifact storage. Map Site content-addressed source IDs and owner IDs to destination
snapshot/user IDs. Preserve original retrieval/check dates and geography vintages,
including Connecticut planning-region versus old-county decennial block IDs. An
interpolated Census suggestion must remain unconfirmed after import. Existing
version 1 exports have no geocoding arrays; do not synthesize missing evidence.
