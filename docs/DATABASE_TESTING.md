# PostgreSQL/PostGIS verification

The normal test suite uses isolated in-memory SQLite for fast checks. Run the same
suite against PostgreSQL/PostGIS before relying on database constraints, locking,
or spatial behavior. The PostGIS-specific test is explicitly skipped on SQLite.

Use a dedicated disposable test server/user with CREATEDB and permission to enable
PostGIS. Never point these variables at the production database or reuse production
credentials. The Django test runner creates and destroys a separate `test_` database.

Set these environment variables for the test server, then run `make test-postgis`:

- `PARAGON_TEST_DB_NAME`: base connection database.
- `PARAGON_TEST_DB_USER`: isolated test user.
- `PARAGON_TEST_DB_PASSWORD`: test password, if required.
- `PARAGON_TEST_DB_HOST`: hostname or private UNIX socket directory.
- `PARAGON_TEST_DB_PORT`: defaults to 5432.
- `GEOS_LIBRARY_PATH` and `GDAL_LIBRARY_PATH`: optional absolute library paths when
  the libraries are installed outside the operating system's standard search path.

This test setting is separate from production and never selected automatically by
the deployment entrypoint. A missing required test database variable stops startup.
The verification exercises migrations, case-insensitive uniqueness, membership,
roles, audit records, and spherical PostGIS distance behavior.

In the current implementation environment, Docker is inaccessible. An isolated
Conda PostgreSQL 17/PostGIS installation under `/tmp` supplies a local-only socket
server for verification. It is test infrastructure, not a deployment solution.
