# DigitalOcean droplet runbook (Release 2.0, items 24-26)

**Host:** one Ubuntu 24.04 droplet (2 GB RAM, 1 vCPU, 50 GB), SFO2. The DigitalOcean Cloud
Firewall allows SSH only from Adi's IP, plus HTTP/HTTPS from anywhere. Hardening: 2 GB
swap (swappiness 10), unattended security upgrades, fail2ban, key-only SSH, Docker log
rotation (10 MB x 3).

**Stack** (`infra/compose.yaml`, run from `/srv/paragon/app`):
- `db`: Postgres 17, tuned for 2 GB, no published port, volume `pgdata`.
- `app`: the Django image running `infra/start_all.py` (Gunicorn, both job clusters,
  scheduler); bound to `127.0.0.1:8000` only; volume `appdata` at `/app/var`; the
  Overture archive mounted read-only from `/srv/paragon/overture-archive`.
- `caddy` (profile `web`): automatic HTTPS for `PARAGON_DOMAIN`, HSTS, CSP,
  Permissions-Policy; the only service with public ports.

**Secrets** stay on the droplet in `/etc/paragon` (mode 600), never in Git:
`app.env` (Django secret, database URL, allowed hosts, SEC contact), `db_password`,
`backup.env` (B2 keys, optional healthchecks.io URL), `compose.env` (`PARAGON_DOMAIN`).

**Deploy / update** (from the Mac):
```sh
COPYFILE_DISABLE=1 git ls-files -co --exclude-standard -z | tar --null -T - -czf /tmp/src.tgz
scp -i ~/.ssh/paragon_droplet /tmp/src.tgz root@DROPLET:/root/
ssh -i ~/.ssh/paragon_droplet root@DROPLET 'cd /srv/paragon && rm -rf app.new && mkdir app.new && tar -xzf /root/src.tgz -C app.new && rm -rf app.old && mv app app.old && mv app.new app && cd app && docker compose -f infra/compose.yaml --env-file /etc/paragon/compose.env --profile web up -d --build'
```

**Baseline (B0, 2026-11-22, idle, 36 seeded properties, no portfolio analysis yet):**

| Measure | Value |
|---|---|
| Host memory | 1,967 MB total; 926 MB used, 1,041 MB available; swap 579 MB used of 2,047 MB |
| Containers | app 478 MB (limit 1.27 GB), db 51 MB (limit 384 MB), caddy 15 MB |
| App processes | one qcluster worker 251 MB (held after a compute), 2 Gunicorn workers ~70 MB each, cluster parents and scheduler 10–51 MB |
| Disk | 8.0 GB used of 48 GB; Docker images 1.15 GB, volumes 677 MB, build cache 1.9 GB (1.3 GB reclaimable) |
| Postgres | 12 MB |
| Rows | 36 locations, 137 snapshots, 10 area sections, 6 signals, 4 jobs |
| Compute timings | demographics 248 s with a first-time state ACS load, 5 s after; area profile 40 s and 18 s |

Decision: the idle app container is under 900 MB, so the foreground cluster keeps 2 workers;
both clusters recycle a worker above `max_rss` 350,000 KB.

**Backups** (`infra/backup.sh`, systemd `paragon-backup.timer`, 07:00 UTC daily): pg_dump
plus the app volume, copied to Backblaze B2 with rclone, 14 days kept; the Overture
archive is copied off-box once. `infra/backup.sh --restore-check` restores the newest dump
into a scratch database and counts locations. DigitalOcean droplet backups are an
optional second layer.

---

# Release 1 runbook (added 2026-11-19, batch D)

**Status:** everything needed to run Release 1 on a regular host is in `main`, and the full local verification is in `docs/TEST_REPORT.md`. **Nothing has been provisioned.** Hosting needs Adi's decision and approval (below).

## What runs
`render.yaml` starts `python infra/start_all.py`. It prepares the release (migrations, source catalog), enables the implemented schedules, then supervises four processes in one container:
- **Gunicorn** (web)
- **Maintenance worker** (`qcluster`): scheduled refreshes
- **Foreground worker** (`Q_CLUSTER_NAME=paragon-foreground qcluster`): screens, computes, brief
- **Scheduler** (`run_scheduler --interval 30`)

All of them are needed because the private evidence disk attaches to one service only. If any process exits, the container exits and the host restarts it. `RUN_BACKGROUND_WORKERS=true` turns on the worker and scheduler.

## Secrets and settings to add in the host
| Variable | Needed for | Notes |
|---|---|---|
| `DJANGO_ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS` | Web | The assigned hostname |
| `ACCESS_BOOTSTRAP_EMAIL`, `ACCESS_BOOTSTRAP_PASSWORD` | First admin sign-in | Remove after the first login (see PASSWORD_ACCESS.md) |
| `SEC_USER_AGENT` | Tenant watch | `"Paragon Radar <contact email>"`; required by SEC fair access. Without it, tenant watch reports NOT_CONFIGURED. |
| `BLS_API_KEY` | Optional | Free BLS v2 key for higher rate limits (v1 keyless works for this portfolio size) |
| `OVERTURE_MEMORY_LIMIT` | Overture captures | `256MB` on a 512 MB plan; raise on larger plans |

## Memory note
DuckDB Overture captures and the worker run beside the web process. On the 512 MB plan, keep `OVERTURE_MEMORY_LIMIT=256MB`. Captures still complete but are slower, and very dense areas (Manhattan: about 145,000 places within 3 miles) may need a 1 GB+ plan. Confirm current pricing before choosing a larger plan.

## ACS for all states (redesign B4a)
New places can be anywhere in the US, so ACS block-group data is ingested for all 50 states and DC:
```sh
python backend/manage.py ingest_acs --all-states --year 2024
python backend/manage.py ingest_acs --all-states --year 2019
```
2024 (table-based) downloads five national files once to `var/acs-cache/2024/` (246 MB, resumable,
excluded from backups) and parses them from disk in batches of at most 30,000 block groups. 2019 reads
one state at a time with HTTP range requests. States already ingested are skipped. Measured on the
preview (18 missing states each): 2024 in 10 s, peak 276 MB; 2019 in 106 s, peak 371 MB.

Analyses never download ACS themselves: a state that is missing queues a background `ingest_acs_state`
job, the demographics section shows "loading", and the job wakes the waiting analyses when it is done.

## First-time data bootstrap (one command, re-runnable)
```sh
python backend/manage.py bootstrap_data --overture-archive /app/var/overture-archive
```
It runs, in order:
1. sync catalog and schedules
2. import the public seed (unconfirmed)
3. import listing tenants (unconfirmed)
4. ingest ACS 2024 for portfolio states and neighbours
5. ingest the ACS 2019 baseline
6. import archived Overture captures
7. compute every section
8. evaluate signals and generate the baseline brief

Steps 4–7 take roughly 20–40 minutes on first run.

**Overture history:** Adi's machine holds 105 archived captures (Sep, Oct and Nov 2026 releases for 35 properties; about 1.3 GB, in `var/overture-archive`). Copy them to the host's disk before running the bootstrap. Overture deletes older releases from its bucket after about two months, so this history cannot be re-downloaded. Without the archive, history starts from the newest release.

## Ongoing schedules (US Eastern)
| Schedule | When | Work |
|---|---|---|
| `sec_daily` | daily 06:00 | Tenant SEC filings |
| `bls_bps_check` | weekly | Economy |
| `overture_check` | weekly | Businesses, capturing every monitored pin |
| `brief_weekly` | Monday 07:00 | This Week brief |
| `annual_sources_check` | monthly | New ACS, LODES and HPMS years |
| `flood_recheck` | monthly | FEMA flood zones and NRI |

`maintenance_daily` and `backup_daily` have no handlers yet and stay visibly blocked. Use the host's database backups.

---

# Deferred regular-host deployment reference

**User decision, 2026-11-19:** stay on the current OpenAI Site without external
hosting. Do not provision this configuration or request its budget as a prerequisite
to feature work. See [TEMPORARY_SITE.md](TEMPORARY_SITE.md) for the active deployment.

The remaining instructions describe a prepared future option, not an approved
migration. The tested `render.yaml` and password implementation are retained for
portability. No external resources have been purchased or provisioned.

## Concrete resource quote

Checked 2026-11-19 against [Render pricing](https://render.com/pricing) and
[compute plans](https://render.com/docs/compute-plans):

| Resource | Configuration | Monthly USD estimate |
|---|---|---:|
| Web | `0.5c-512mb`, one instance/one Gunicorn worker | $7.00 |
| PostgreSQL | `0.1c-256mb`, 1 GB disk | $6.00 compute |
| Database storage | 1 GB, autoscaling disabled | Up to $0.30 |
| Private evidence disk | 5 GB at $0.25/GB | $1.25 |
| Hobby workspace | No paid workspace upgrade | $0.00 |
| Total initial host | Before tax/usage overages | **Budget $14.55/month** |

Pricing mentions 1 GB included database storage; the budget conservatively includes
$0.30 until the creation screen confirms the actual charge. Explicit 1 GB storage
avoids Render's larger default allocation. There is no custom domain purchase.
Confirm the resource summary before creation; stop if it exceeds this scope.
Bandwidth/build overages, future background workers, independent backups, larger
source history, and a larger compute tier are outside this initial estimate.
Do not enable automatic storage growth or paid upgrades without approval.

Free Render web services cannot attach the required persistent disk, and free
Postgres expires after 30 days. They are unsuitable for this retained workspace.
See [free limits](https://render.com/docs/free) and
[persistent disks](https://render.com/docs/disks). No resources have been purchased.

**Owner approval is required before provisioning.** AGENT_HANDOFF §0.1 says to
“get Amit's or Adi's approval before any paid plan”; §4.8 prohibits paid sign-ups
without explicit approval. Deployment also needs an owner-connected Render account
with access to this repository. Do not put hosting tokens or passwords in Git/chat.

## Build and deploy

1. Verify the exact release commit with backend/PostGIS tests and the frontend build.
   Validate `render.yaml` against `https://render.com/schema/render.yaml.json`.
2. With Docker access, build the image and smoke it against disposable PostGIS.
   Container execution remains unverified in the current environment because Docker
   is unavailable; local production settings/Gunicorn tests do not replace this check.
3. After cost approval and owner account connection, create a Blueprint from this
   repository. Automatic deployment is **off**: release tested commits manually while
   the GitHub OAuth credential lacks workflow scope.
4. Enter `DJANGO_ALLOWED_HOSTS` as the assigned hostname and
   `CSRF_TRUSTED_ORIGINS` as its `https://` origin. Keep the generated Django secret.
   The database connection is injected over Render's private network; external
   database access is disabled. PostGIS is supported on this PostgreSQL version.
5. Enter the approved administrator email and a generated strong password as
   `ACCESS_BOOTSTRAP_EMAIL` and `ACCESS_BOOTSTRAP_PASSWORD` in the host secret store.
   They provision a named account once. They never reset, elevate, or reactivate an
   existing account. Remove both secrets after verified login; subsequent restarts
   require an active password administrator. See [PASSWORD_ACCESS.md](PASSWORD_ACCESS.md).
6. Startup runs `prepare_release` after the disk mounts, under a PostgreSQL advisory
   lock: migrate, sync source definitions, optionally import a checksum-verified
   private workspace, seed missing public properties, sync disabled schedules, and
   bootstrap access. Gunicorn starts only after success. The password is removed
   from its environment. No migration export or password enters the image.
7. Verify the disk is writable by the non-root application user. The startup write
   check fails closed if not. Only `/app/var/artifacts` persists. Nothing under that
   directory is served by WhiteNoise or an unauthenticated API. Render disks are
   unavailable during pre-deploy; there is deliberately no pre-deploy import.
8. For the first migration, upload the private export through the owner's secure
   host shell/file facility. Set `WORKSPACE_IMPORT_PATH` to that private file and
   `WORKSPACE_IMPORT_SHA256` to its independently checked digest, then restart.
   Alternatively run `import_site_workspace` manually, first dry-run then `--apply`.
   Follow [WORKSPACE_MIGRATION.md](WORKSPACE_MIGRATION.md), including fresh-export
   comparison before cutover. Do not accept user edits at the destination first.
   Remove the optional import environment pair after receipt verification; the
   retained private content-addressed export remains available for recovery.
9. Deliver the URL and credentials privately only after acceptance. Add approved
   additional named accounts with `set_access_password`, using the hidden prompt.
   Password rotation and membership revocation require no source change. Never
   automatically reactivate a revoked membership during release startup.

## External acceptance before cutover

From a browser without ChatGPT sign-in: HTTPS works, root shows only password login,
wrong password denies access, anonymous business APIs return no data, correct login
loads the real 36-property portfolio, notes/pins/history match the latest export,
logout denies API access, and password rotation/revocation takes effect. Verify
restart persistence of database records, sessions, and private artifacts. Check
rate limits and real ingress behavior; the local socket smoke cannot verify TLS.
Render's ingress must sanitize the trusted forwarded-protocol header before
`TRUST_PROXY_SSL_HEADER=true` is used. Sign-in throttling uses `REMOTE_ADDR` unless
`TRUSTED_PROXY_COUNT` is set to the number of reverse proxies that append to
`X-Forwarded-For` (Caddy on the droplet: `1`); entries left of those hops are ignored.

Security settings (R2 item 2): sessions expire after 12 hours idle and 14 days in total;
`EXPENSIVE_RATE` (default `120/hour`) caps per-user screens, recomputes and SEC searches;
`/health/ready/` checks the database. `LOCAL_PREVIEW` and `LOCAL_SHARED_PASSWORD` are
local-preview-only: production settings refuse to start if either is set, and the shared
password is refused for any request carrying a forwarding header.

Current evidence: 253 backend tests pass on PostgreSQL 17/PostGIS 3.6; the manifest
passes Render's official schema. Password browser QA and a private 36-record import
smoke pass. The actual production startup also passes a disposable PostGIS smoke:
private import, wrong/correct password, secure HttpOnly cookies, anonymous denial,
logout, two process starts, session/note persistence, and artifact checksum. Record final image/build/HTTPS/restart checks in TEST_REPORT after deploy.

## Operational limits and rollback

This initial host is for password access and migration. It does not run Q2 workers
or the continuous scheduler, enable missing source handlers, or constitute Release 1.
Independent artifact/database backup and restore verification, background source
jobs, all P0 workflows, and production acceptance remain mandatory. A Render disk
belongs to one service and cannot be shared with a separate worker. Prepare approved
object storage or another supported durable arrangement before scaling ingestion.
The small compute plans require actual load checks before broader use.

Disk-backed services have deployment downtime. Retain the previous image and use
additive migrations. Roll back application code only while compatible with the
current schema; take database and artifact backups before data-changing releases.
Do not blindly reverse migrations against valuable data. Do not retire the Site
until the owner confirms the replacement and migrated data.
