"""T2: scheduled refresh handlers select monitored locations and are idempotent."""
from datetime import datetime, timezone
from email.message import Message
from pathlib import Path
from urllib.error import HTTPError
import io
import pytest
from apps.area import refresh
from apps.area.http import SourceError

pytestmark = pytest.mark.django_db


class Ctx:
    beats = 0
    def heartbeat(self):
        Ctx.beats += 1


def locations():
    from apps.locations.service import create_location, change_pin
    made = []
    for name, status, pin in [('Owned A', 'owned', (41.1, -73.4)), ('Candidate B', 'candidate', (41.2, -73.5)),
            ('Archived C', 'archived', (41.3, -73.6)), ('Unplaced D', 'owned', None)]:
        loc = create_location(name=name, address='1 Main St', actor=None)
        loc.status = status
        loc.save()
        if pin:
            loc = change_pin(location_id=loc.pk, expected_version=loc.version, lat=pin[0], lon=pin[1], actor=None)
        made.append(loc)
    return made


def test_monitored_excludes_archived_and_unplaced():
    locations()
    assert [l.name for l in refresh.monitored()] == ['Candidate B', 'Owned A']


def test_handlers_recompute_each_monitored_location_and_survive_failures(monkeypatch):
    locations()
    calls = []

    def fake(location_id, *, sections, **kw):
        calls.append(sections)
        if len(calls) == 2:
            raise SourceError('SOURCE_ERROR')
        return []
    monkeypatch.setattr('apps.area.service.compute_area', fake)
    out = refresh.refresh_economy(Ctx())
    assert (out.done, out.failed) == (1, 1) and list(out.failures.values()) == ['SOURCE_ERROR']
    assert calls == [('economy',), ('economy',)]
    calls.clear()
    assert refresh.refresh_hazards(Ctx()).done == 1 and calls[0] == ('hazards',)


class Probe:
    """Serves ACS bulk-file probes: only the listed years exist."""
    def __init__(self, years):
        self.years, self.urls = years, []
    def open(self, request, timeout=None):
        self.urls.append(request.full_url)
        if any(f'/{y}/table-based' in request.full_url for y in self.years):
            return io.BytesIO(b'GEO_ID|B01003_E001|B01003_M001\n')
        raise HTTPError(request.full_url, 404, 'Not Found', Message(), None)


class Resp(io.BytesIO):
    status = 200
    def __enter__(self): return self
    def __exit__(self, *a): return False


def test_newest_acs_year_detection():
    from datetime import date
    class P(Probe):
        def open(self, request, timeout=None):
            r = super().open(request, timeout)
            return Resp(r.read())
    assert refresh.newest_acs_year(opener=P([2024]), today=date(2026, 11, 19)) == 2024
    assert refresh.newest_acs_year(opener=P([2025, 2024]), today=date(2026, 12, 20)) == 2025
    assert refresh.newest_acs_year(opener=P([]), today=date(2026, 11, 19)) is None


def test_overture_check_records_release_health(monkeypatch):
    from apps.sources.catalog import sync_catalog
    from apps.sources.models import SourceHealth
    sync_catalog()
    locations()
    monkeypatch.setattr(refresh.overture, 'available_releases', lambda opener=None: ['2026-10-21.0', '2026-11-18.0'])
    monkeypatch.setattr('apps.area.service.compute_area', lambda *a, **k: [])
    out = refresh.refresh_businesses(Ctx())
    assert (out.done, out.failed, out.info['release']) == (2, 0, '2026-11-18.0')
    assert SourceHealth.objects.get(source_id='SRC-13', scope='releases').last_success_at is not None


def test_scheduled_handlers_are_registered_for_schedules():
    from apps.operations.registry import REGISTRY
    assert {'bls_bps_check', 'overture_check', 'flood_recheck', 'annual_sources_check'} <= set(REGISTRY)
