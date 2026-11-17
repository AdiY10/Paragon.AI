.PHONY: install test check
install:
	uv sync --locked

test:
	uv run --locked pytest

check:
	uv run --locked python backend/manage.py check --settings=config.settings.test
