# Public portfolio import

After migrations and `sync_sources`, run `python backend/manage.py import_portfolio`.
The deployment pre-deploy command performs this idempotent import automatically.
It requires exactly seed IDs P01 through P36 and validates the entire CSV before
writing properties. The source row serializes competing importers on PostgreSQL.

Every new seed location is Owned and Unconfirmed, with its public source URL and
source-as-of date. Reference pins are explicitly labelled seed_reference; they are
not newly verified geocodes or user-confirmed building locations. Mt. Kisco remains
unplaced because its source coordinate pair is missing. The documented Nominatim
reference retains OpenStreetMap attribution. Asset classification preserves its
original inferred label alongside the normalized application category.

The importer does not load listing demographics, traffic counts, occupancy claims,
or GLA as measured values. GLA and user notes remain absent. Tenant roster import is
a separate pending work package; names are not silently treated as confirmed tenants.

A SHA-256 import batch ties each new property to the exact validated file bytes.
Reruns retain existing properties, edits, confirmations, pins, and archive decisions.
They do not reset source dates or import times. A new file revision may create an
additional batch record but does not overwrite existing seeded locations.

Verified locally: first import created 36 unconfirmed properties with 35 reference
pins; second import created zero and retained all 36; only one batch remained.
PostgreSQL concurrency tests also verify that simultaneous imports create one
portfolio and one batch. This does not constitute deployed AC-03 acceptance.
