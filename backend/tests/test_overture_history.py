"""Redesign B2: moving the captured Overture history (owned pins only) to another server."""
import tarfile
import pytest
from apps.area import overture_store as ostore
from apps.area.models import OvertureCapture, OvertureReleasePair
from apps.sources.storage import LocalArtifactStore
from backend.tests.test_signals import placed

pytestmark = pytest.mark.django_db
RELEASES = ['2026-09-23.1', '2026-10-21.0', '2026-11-18.0']


def rec(i, lat, lon):
    return {'id': f'p{i}', 'name': f'Place {i}', 'basic_category': 'restaurant', 'brand': None, 'brand_wikidata': None,
        'operating_status': 'open', 'confidence': 0.95, 'lat': lat, 'lon': lon, 'sources': [{'big': 'x' * 50}]}


def seed(store):
    owned = placed('Owned', 41.0, -73.0)
    screen = placed('Screen', 42.0, -74.0, status='candidate')
    screen.screening = True
    screen.save()
    for release in RELEASES:
        ostore.store_capture(41.0, -73.0, release, [rec(i, 41.0, -73.0) for i in range(3)], store)
        ostore.store_capture(42.0, -74.0, release, [rec(9, 42.0, -74.0)], store)
    return owned, screen


def test_export_owned_pins_then_import_on_a_fresh_server(tmp_path):
    from apps.locations.models import Location
    preview = LocalArtifactStore(tmp_path / 'preview')
    seed(preview)
    out = tmp_path / 'history.tar'
    owned = Location.objects.filter(status='owned', screening=False).select_related('current_revision')
    assert ostore.export_history(list(owned), preview, out) == 3
    with tarfile.open(out) as tar:
        names = tar.getnames()
        manifest = tar.extractfile('manifest.jsonl').read().decode()
    assert len(names) == 2 and 'Owned'  # one shared file (identical content) + manifest not in manifest and '42.000000' not in manifest  # owned pins only, no names
    # "Production": the same database rows gone, an empty artifact store.
    OvertureCapture.objects.all().delete()
    OvertureReleasePair.objects.all().delete()
    production = LocalArtifactStore(tmp_path / 'production')
    assert ostore.import_history(out, production) == (3, 0)
    rows = OvertureCapture.objects.order_by('release')
    assert [r.release for r in rows] == RELEASES and all(r.raw_pruned and r.summary['imported'] for r in rows)
    assert len(ostore.load(rows[0], production)) == 3 and 'sources' not in ostore.load(rows[0], production)[0]
    assert OvertureReleasePair.objects.count() == 2
    assert ostore.import_history(out, production) == (0, 3)  # re-running keeps what is there


def test_a_tampered_file_is_refused(tmp_path):
    from apps.locations.models import Location
    store = LocalArtifactStore(tmp_path / 'a')
    seed(store)
    out = tmp_path / 'history.tar'
    ostore.export_history(list(Location.objects.filter(status='owned').select_related('current_revision')), store, out)
    bad = tmp_path / 'bad.tar'
    with tarfile.open(out) as src, tarfile.open(bad, 'w') as dst:
        for member in src.getmembers():
            data = src.extractfile(member).read()
            if member.name.startswith('captures/'):
                data = data[:-1] + bytes([data[-1] ^ 1])
            import io
            member.size = len(data)
            dst.addfile(member, io.BytesIO(data))
    OvertureCapture.objects.all().delete()
    with pytest.raises(ostore.HistoryError):
        ostore.import_history(bad, LocalArtifactStore(tmp_path / 'b'))


def test_compact_snapshots_are_not_mistaken_for_raw_captures(tmp_path, monkeypatch):
    from apps.sources.models import SourceSnapshot

    class Snap:
        context = {'format': 'compact', 'coordinates': {'lat': 41.0, 'lon': -73.0}, 'radius_miles': 3}
    monkeypatch.setattr(SourceSnapshot.objects, 'filter', lambda **kw: type('Q', (), {'order_by': lambda self, *a: [Snap()]})())
    assert ostore._raw_snapshot(41.0, -73.0, RELEASES[0]) is None
