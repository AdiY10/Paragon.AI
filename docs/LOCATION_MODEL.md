# Location revisions and edits

Locations distinguish Owned, Candidate, and Archived status, confirmation, source
provenance, and optional user-entered GLA. Unknown GLA is null, never zero. Creation
may retain an unplaced pin; it does not invent coordinates or infer confirmation.

Pins are immutable numbered revisions. Seed references, Census exact/non-exact
matches, Nominatim, and manual edits have distinct method labels. A public reference
must not be displayed as a newly verified geocode. Ownership and pin confirmation
are separate actions and are attributed independently.

All edits use an expected location version under a row lock. Conflicting editors
receive a domain conflict rather than overwriting one another. A separate analysis
version changes for pin/ring inputs, while notes and other descriptive edits leave
it intact. Future profile jobs must retain their input revision/version and reject
obsolete results; metric computation is not implemented by the location model itself.

Coordinates are canonical finite double-precision latitude/longitude values with
pair/range constraints. The small location table does not need its own spatial index;
ring/reference-geography queries will use indexed PostGIS geography assets. This
keeps isolated SQLite tests available without weakening actual PostGIS verification.

Locations are archived rather than deleting provenance. Revision numbers are unique
per location, cross-location current-revision pointers fail validation, and audit
records retain actor and changed fields. No property financial results are inferred
from these records.
