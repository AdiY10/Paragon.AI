# Durable jobs and workers

Jobs are submitted only through a code-defined registry; callers cannot supply a
Python function path. The initial registered job is `sync_source_catalog`, which
synchronizes documented metadata. It does not fetch external metrics or claim a
successful data-source check. Source-specific handlers are added with integrations.

## Submission and execution

`enqueue_job` creates a domain JobRun and signed Django-Q2 ORM message inside one
PostgreSQL transaction. `(kind, scope, dedup_key)` is unique. Identical submissions
reuse one job and one queue message; unknown parameters and handlers are rejected.
Only the job UUID crosses the transport boundary.

Execution acquires a database lease, assigns an attempt token, and updates heartbeat
and run timestamps. Completed jobs do not execute again. Active leases reject duplicate
execution; expired leases can be reclaimed. An old attempt token cannot overwrite a
new attempt's final run state. Handlers must make their own source writes idempotent:
leases do not make external side effects exactly-once.

Failures store sanitized codes, never raw exception text. Retryable failures are bounded
to three domain attempts, with exponential minimum backoff. Django-Q2 receipt timeouts
can make actual retries later than that minimum. Nonretryable and exhausted failures are
terminal domain failures and can be acknowledged by the transport; transport success is
not equivalent to a successful business job.

## Queues

The database broker needs no Redis service. Start the maintenance worker with:

```sh
python backend/manage.py qcluster
```

Maintenance has one worker, a 1,800-second hard timeout, a 1,830-second application
lease, and a 2,100-second receipt retry. Foreground capacity is reserved with an alternate
cluster: `Q_CLUSTER_NAME=paragon-foreground python backend/manage.py qcluster`.
Its hard timeout is 90 seconds and receipt retry is 150 seconds. No foreground product
handler is registered yet. Bulk ingestion must be chunked; do not put unbounded national
imports into a single job or execute them inside web requests.

The built-in Q2 recurring scheduler is disabled. A timezone-aware application scheduler
and recovery sweep are still pending; do not claim scheduled refreshes are running.
The remaining recovery work must handle domain rows whose transport retries were exhausted
or whose worker died without finalizing their lease.

## Verification

The PostGIS suite covers atomic queue rollback, deduplication under concurrent submission,
redelivery after a lost receipt, bounded retries, terminal failures, active/expired leases,
result idempotency, and stale-attempt protection. SQLite skips the concurrency and spatial
checks explicitly.

With production settings pointed at an explicitly configured disposable database, run:

```sh
uv run python scripts/verification/worker_smoke.py
```

This enqueues the real metadata-sync handler, starts a real worker, waits for domain and
transport completion, then asks the worker parent to drain its children. Forced termination
fails the check rather than being reported as graceful shutdown. The verified local run
processed 16 source definitions in one attempt, acknowledged the message, and shut down
cleanly. This does not verify deployment schedules or production source freshness.
