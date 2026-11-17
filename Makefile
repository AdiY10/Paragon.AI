.PHONY: install test check
install:
	uv sync --locked

test:
	uv run --locked pytest

check:
	uv run --locked python backend/manage.py check --settings=config.settings.test

# Configure PARAGON_TEST_DB_* variables for an isolated PostGIS server first.
test-postgis:
	uv run --locked pytest --ds=config.settings.postgres_test
