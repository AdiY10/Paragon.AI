# Private location management

Active Admins and Members can manage locations. Anonymous and removed users are
denied by the session/membership stack. Browser mutations require CSRF protection.

- `GET /api/locations/` returns paginated non-archived records by default. Filters:
  state, asset_type, and status (including archived or all).
- `POST /api/locations/search/` accepts search text in JSON body field `q`, with the
  same optional filters. Search text is rejected on list URL query parameters.
- `POST /api/locations/` creates a user-entered candidate/address record, initially
  unplaced unless a subsequent verified lookup or manual pin supplies coordinates.
- `GET /api/locations/<id>/` returns the current record, pin revision, and provenance.
- `PATCH /api/locations/<id>/` requires expected_version and editable fields. Stale
  edits return 409. Status changes support archiving without deleting history.
- `POST /api/locations/<id>/pin/` requires expected_version, lat, and lon. It creates
  a manual revision; callers cannot impersonate Census or another provider. Pin
  confirmation is distinct from ownership confirmation.
- `POST /api/locations/<id>/confirm/` records explicit, attributed confirmation.
- `GET /api/locations/<id>/history/` exposes paginated actor-attributed changes.

Read-only fields and unknown mutation inputs are rejected. Invalid/non-finite pins,
missing versions, zero GLA, and stale writes fail visibly. Current revision IDs and
analysis versions prepare profile workers to reject stale results.

This layer manages location records only. Creating or editing address text does not
yet perform geocoding, and pin changes do not yet run the profile calculation pipeline.
No demographic values, signals, or source-success claims are synthesized to fill that
gap. The Census/fallback workflow and numerical profiles remain the next work packages.

Verification includes private access, Members' edit rights, source-bearing seeded
records, real portfolio search/state filters, confirmation/archive/history, pin changes,
forged input rejection, optimistic conflicts, and CSRF. The production Gunicorn smoke
also verifies anonymous denial on locations, sources, jobs, and schedules.
