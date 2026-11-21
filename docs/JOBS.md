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

Maintenance (scheduled refreshes, SEC, `maintenance_daily`) has one worker, a 7,200-second
hard timeout and a 7,500-second receipt retry. The foreground cluster runs user-triggered
work (`compute_area_profile`, `compute_ring_demographics`, `brief_weekly`) so it never waits
behind a refresh: `Q_CLUSTER_NAME=paragon-foreground python backend/manage.py qcluster`,
two workers, 1,200-second timeout, 1,500-second retry. The receipt retry always exceeds the
timeout so a running task is never re-delivered. Attempts hold a 600-second lease that every
`heartbeat()` renews; a recovered (fenced) attempt stops at its next heartbeat. Only one
Overture DuckDB scan runs at a time (`area/locks.py`, a Postgres advisory lock). Bulk ingestion must be chunked; do not put unbounded national
imports into a single job or execute them inside web requests.

The built-in Q2 recurring scheduler is disabled. The application scheduler is documented
in SCHEDULER.md and uses Eastern wall time, persisted occurrences, and leader leases.
Source handlers remain disabled until implemented. The recovery sweep described in JOB_RECOVERY.md handles lost messages and expired
attempts under bounded limits. No production refresh schedule is claimed running.

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

## Administrator controls

`GET /api/admin/jobs/` returns paginated run metadata, timing, record counts, retry
state, and sanitized error codes. It omits handler parameters and transport payloads.
`POST /api/admin/jobs/` submits a registered kind with a UUID `Idempotency-Key` header;
repeating the request returns the same run. The initial catalog job uses global scope.

`POST /api/admin/jobs/<id>/rerun/` requires a new UUID idempotency key and a terminal
original run. It creates a linked run with the requesting administrator recorded,
leaving the original result intact. Active runs return 409 and remain under lease/
recovery control. Removed or Member users cannot access these endpoints. Browser
mutations remain protected by the session authentication and CSRF stack.
