# Eastern-time scheduler

`sync_schedules` validates and loads the eight versioned definitions in
`config/schedules.yaml`. New definitions are disabled by default. The optional
`--enable-available` flag enables only code-registered handlers; missing handlers
stay disabled and the private admin API labels them HANDLER_NOT_IMPLEMENTED.
There are no placeholder source-refresh or backup handlers.

Start the scheduler with `python backend/manage.py run_scheduler`. It uses a
renewable PostgreSQL leadership lease and locks each due schedule before enqueue.
SIGINT/SIGTERM request a graceful stop and release the lease; an interrupted process
can be replaced after its lease expires. `--once` performs one tick and releases
leadership for external orchestration and verification.

Each dispatch atomically records its occurrence, enqueues its durable job, and
advances the cursor. An enqueue failure rolls back the occurrence and cursor.
The unique local-date occurrence prevents duplicate work even if a cursor is rewound.
Concurrent scheduler candidates cannot enqueue the same occurrence twice.

Daily, weekly, and monthly rules resolve in America/New_York. The spring gap uses
the first valid minute; repeated fall times run once at their first occurrence.
Missed runs coalesce into the most recent due occurrence, retaining the original
due time, dispatch delay, missed count, calendar, and linked job. Brief generation
must use those fields to mark late delivery when its handler is implemented; it
must not label a historical cutoff as a newly detected event.

`GET /api/admin/schedules/` exposes definitions, next due time, last dispatch,
missing-handler status, and the scheduler's last tick to active Admins only.

Verification: 108 tests pass on real PostgreSQL/PostGIS, including competing leader
candidates, expired-leader recovery, DST, cursor replay, and enqueue rollback. A real
local catalog-sync occurrence was dispatched, completed through the ORM worker, and
acknowledged with graceful worker shutdown. Its verification schedule was disabled
afterward. This metadata-sync verification is not a claim that SEC/Overture/BLS jobs,
backups, or weekly briefs are implemented or running in production.
