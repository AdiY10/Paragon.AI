# Moving the temporary workspace to Django

The importer preserves a complete single workspace, including edits, notes, current
and historical pins, and audit history. Imported actor labels are evidence only;
they never create users or grant access. The complete original JSON is retained in
private content-addressed storage, with an immutable SHA-256 receipt in PostgreSQL.
Do not commit exports: they can contain private notes and addresses.

The captured workspace on 2026-11-19 contained 36 seed properties, 35 reference pins,
one unplaced property, and no user edits, audit events, or Census lookups. Its SHA-256
is `eadae4ecbd0c616bfc406534cfe985f9d38f141b7741efcb0ec98a8a179e7036`.
A disposable-database smoke check imported all 36, compared every business field and
current pin/date, replayed the export without changes, and confirmed the public seed
command creates no duplicates. This is a point-in-time backup, not a completed cutover.

## Cutover procedure

1. Ask current users to stop editing the temporary workspace during cutover. Export
   the intended workspace and retain its checksum privately. Sites workspaces are
   per-user: do not merge exports belonging to different people automatically.
2. Require schema 3 when historical audits or revisions exist. Earlier exports omit
   their location links; the importer rejects these instead of guessing. A complete
   native table capture with explicit location links is also supported. Schema 1/2
   exports without such history are accepted.
3. With a fresh destination database and durable private artifact storage mounted,
   run migrations and `sync_sources`, then validate:

   ```sh
   python backend/manage.py import_site_workspace /private/workspace.json
   ```

4. Review counts/checksum, then repeat with `--apply`. Run `import_portfolio`
   afterwards; it fills missing public seed rows without overwriting imported data.
   Import before seeding to retain original pin timestamps directly. A pristine,
   already-seeded destination may reuse matching immutable initial reference pins;
   its original seed timestamps remain, with original Site dates in the retained export.
5. Confirm notes, pins, unplaced properties, confirmation flags, and history through
   the password-protected UI/API. Census raw bytes are revalidated and archived with
   original retrieval dates; importing does not imply a fresh source check.
6. Obtain a new export/checksum before final cutover and compare it with the imported
   export. If it changed, use a fresh target and the latest export. The importer
   refuses to overwrite destination edits or combine conflicting source histories.
7. Verify HTTPS, wrong-password denial, unauthenticated API denial, login, logout,
   restart persistence, and password rotation from a browser without ChatGPT sign-in.
   Deliver the URL and account credentials privately. Retire the temporary Site only
   after these checks and the workspace owner confirms the migrated data.

Exact-file replay is safe even after subsequent Django edits. Different exports are
not an incremental sync mechanism. New revision timestamps and historical source
checks retain their original dates; original workspace IDs remain evidence metadata.

Run the private smoke check locally (output contains only counts and checksum):

```sh
.venv/bin/python scripts/verification/workspace_import_smoke.py /private/workspace.json
```

The smoke check uses a disposable database and artifact directory, deleted on exit.
No live destination is modified. Keep independent database and artifact backups;
a receipt alone cannot reconstruct the private export bytes.
