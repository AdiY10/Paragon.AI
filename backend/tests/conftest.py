

import pytest as _pytest


@_pytest.fixture(autouse=True)
def _no_auto_acs_ingest(monkeypatch):
    """Tests never download national ACS files; missing ACS rows must surface as NOT_COVERED."""
    monkeypatch.setattr('apps.demographics.service.AUTO_INGEST', False)
