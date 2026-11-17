# Source operations

`sync_sources` loads the versioned metadata catalog; it never claims ingestion or
successful source checks. Source status remains “Not checked” until a real check is
recorded. Metadata synchronization does not reset implementation versions or history.

## Snapshot publication

Adapters return a complete validation report and a binary raw response. Publication
persists the artifact first, then the immutable snapshot. Idempotent reruns reuse
the same content and preserve its original retrieval time. Changed content remains
as a separate revision. Schema/provenance conflicts, partial data, or storage errors
prevent publication. An interrupted DB transaction can leave an unreferenced artifact;
it cannot publish a row pointing to a partial upload. Do not delete retained history
as routine cleanup.

Source links strip query strings, fragments, and credentials. Exact public source
records and geographic context live in private artifacts/snapshot metadata. Artifacts
are not served as public static files.

## Preserved Overture history

After migrations and `sync_sources`, use a durable private store path:

```sh
python backend/manage.py import_overture_captures --directory <archive-root> --store-root <private-store-root>
```

The importer validates each archived manifest, checksum, schema, IDs, count, pin,
three-mile radius, status, confidence, and attribution structure before publication.
It retains the original unconfirmed seed pin provenance. It does not confirm ownership
or tenancy. A failed file stops the command with a nonzero exit; completed snapshots
remain reusable on the next run.

The verified local import contains 70 snapshots for 35 resolved seed pins. Mt. Kisco
has no resolved pin and is not included. Original captures remain local until an
approved durable off-machine store is connected; retention/recovery is not complete.

## Health and freshness

Checks are immutable and idempotent by `(source, scope, run_key)`. Health is scoped
by geography/location so one successful county cannot hide another failing county.
Failures keep the last-good snapshot and its original dates. Two consecutive failures
or Stale status set `needs_alert`; delivery through an external alert channel is still
pending operational integration.

Freshness measures elapsed time since the actual successful source check, using doc
04's per-source windows. Unchanged successful checks can advance the check date;
they do not advance a data period. An Overture release left unprocessed for more than
14 days is stale even if the release-listing check succeeds. Unknown publication dates
use first detection as the conservative recorded availability timestamp.

Historical replay can supply an old cache but cannot clear a newer failure. Out-of-order
check history reconciles the failure streak by actual completion times. A simultaneous
success/failure remains visibly failing. Reimporting archives records their original
retrieval timestamps and does not make them appear freshly checked today.

The private `/api/sources/` endpoint returns scoped health plus an aggregate status.
Any known Failing scope takes precedence, then Stale, then Not checked, then OK.
Coverage of all monitored locations still needs the location/job integration; an OK
status for a known scope is not a claim that every US location is covered.
