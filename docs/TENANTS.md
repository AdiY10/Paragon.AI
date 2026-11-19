# Tenant records and review

The canonical tenant domain is implemented; seed import, APIs, and UI follow next.
A roster record describes a brand/occupant claim, not a legal parent company,
property occupancy rate, rent roll, or a confirmed SEC filer mapping.

Each record has a name, nullable anchor flag (unknown is not false), confirmation,
archive state, source/context, version, and attributed history. User-created records
start unconfirmed. Confirmation is a separate action. A renamed tenant loses its
confirmation, while historical names/source context remain available. Archiving is
reversible and preserves evidence, but restoration never restores old confirmation.

Mutations lock the parent location, reject stale tenant versions, advance the
location version/analysis generation, and append tenant/property audit events.
Creation uses an explicit UUID submission key: replay returns the same record
without overwriting edits; reusing the key for different original data is rejected.
Active names deduplicate only within a location using Unicode/whitespace/case and
apostrophe normalization. Brand aliases, punctuation variants, and corporate parents
are not automatically merged. A normalized SHA-256 key avoids oversized Unicode
index entries while retaining the supplied display name.

Only owned properties permit roster changes. Address/locality changes retire the
old active roster with audit history, alongside the existing pin/ownership reset;
old businesses must not follow the property record to a different address. Invalid
address changes roll back tenant invalidation too. Archived tenants cannot be
confirmed, and another active record with the same name prevents restoration.

The model deliberately has no writable CIK field. SEC mapping requires its own
explicit company selection/confirmation workflow. No guessed public-company parent,
healthy tenant-watch state, or fabricated filing history is provided.
