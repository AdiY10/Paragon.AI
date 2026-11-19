# Regular-host password workspace — prepared, not provisioned

Adi's priority is a normal HTTPS URL that does not require ChatGPT. The initial
`render.yaml` provisions one Docker web service, PostgreSQL 17/PostGIS, and a private
5 GB disk. It enables named password access and retains the optional OIDC path.
The existing temporary Site stays available until the new host passes acceptance.

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
`TRUST_PROXY_SSL_HEADER=true` is used. IP throttling deliberately ignores arbitrary
forwarded-IP headers and can share an ingress-IP budget.

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
