# Deployment — prepared, not yet provisioned

This repository now includes a Node-built React UI, collected WhiteNoise assets, a non-root Python container, Gunicorn configuration,
a disposable local PostGIS Compose service, and a Render web-service blueprint.
The full Release 1 worker/storage/scheduler topology is still being implemented.
No deployed URL or completed production acceptance is claimed.

## Current verification

- The production Django settings, migrations, and Gunicorn entrypoint were exercised
  against isolated local PostgreSQL 17/PostGIS 3.6.
- A private-socket HTTP smoke test verified health 200, app redirect to sign-in,
  anonymous API denial, sign-in rendering, and HSTS.
- The Render manifest validates against Render's official JSON schema.
- Container image build and Compose startup remain unverified: this environment
  cannot access the Docker daemon. These are explicit remaining checks.

## Owner prerequisites and cost

The prepared web service uses Render's paid Starter plan. Do not provision it
without the owner's explicit cost approval. The previously researched estimate
is $7/month for this web service alone. It excludes PostgreSQL, the required
long-running worker, durable source storage, bandwidth, and seven-day backups.
A complete resource quote must be prepared and rechecked before provisioning.
The current blueprint deliberately accepts an externally provisioned PostGIS
`DATABASE_URL`; it creates no database or worker and is not the complete topology.

The owner must supply hosting/repository access and these secrets/configuration:
`DJANGO_ALLOWED_HOSTS`, `DATABASE_URL`, `CSRF_TRUSTED_ORIGINS`, and the three OIDC
settings documented in AUTHENTICATION.md. Render can generate `DJANGO_SECRET_KEY`.
Only enable `TRUST_PROXY_SSL_HEADER=true` when the ingress strips incoming
client-supplied forwarding headers. The app then trusts `X-Forwarded-Proto` for
HTTPS detection. Keep all credentials in the hosting secret store.

## Build and release

1. Run the offline and PostGIS suites for the exact release commit.
2. With Docker access, build `docker build -t paragon-radar:<commit> .` and smoke
   test the image against a disposable PostGIS database. The image defaults to
   production settings and will reject missing configuration.
3. After cost/access approval, create the Render blueprint from `render.yaml` and
   configure an existing approved PostGIS connection.
4. The pre-deploy command applies versioned migrations before traffic switches.
5. Run `python backend/manage.py invite_admin <owner-email>` once through the
   platform shell. No passwords or auth bypass are created.
6. Validate HTTPS, real OIDC callback, revocation, and source-free anonymous routes.
7. Keep auto-deploy gated on passing checks. The GitHub credential currently lacks
   workflow scope, so CI publication must be resolved before automatic releases.

Application checks alone are not sufficient to declare Release 1 ready. Source
jobs, retained history, production backups, performance, and all 25 acceptance
criteria remain required by docs/07.

## Rollback

Retain the previous image/commit. Application rollback is safe only while its code
is compatible with the current schema. Use additive migrations and defer destructive
changes. Before a migration that changes data semantics, take and verify a backup.
Do not attempt a blind reverse migration against valuable production data.

## Local database and smoke command

`compose.yaml` provides a disposable database on localhost port 55432. Set
`PARAGON_LOCAL_DB_PASSWORD` locally; never use production credentials. Compose has
not been started in the present environment. The local isolated verification used
an equivalent socket-only PostgreSQL server instead.

Build the frontend and run `uv run python backend/manage.py collectstatic --noinput` first. With production environment variables supplied and a migrated disposable database:

```sh
uv run python scripts/verification/production_smoke.py
```

This starts the actual Gunicorn entrypoint on a private temporary UNIX socket,
verifies anonymous route behavior, and shuts the process down. It does not complete
a real provider login and does not replace HTTPS deployment verification.
