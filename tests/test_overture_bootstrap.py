import importlib.util
from pathlib import Path
import hashlib
import json
import pytest

spec = importlib.util.spec_from_file_location('bootstrap', Path(__file__).parents[1]/'scripts/ingestion/overture_bootstrap.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

def test_latest_patch_for_each_month():
    xml = b'<r xmlns="http://s3.amazonaws.com/doc/2006-03-01/"><Prefix>release/</Prefix><Prefix>release/2026-09-23.0/</Prefix><Prefix>release/2026-09-23.1/</Prefix><Prefix>release/2026-10-21.0/</Prefix></r>'
    assert m.monthly_releases(xml) == ['2026-09-23.1', '2026-10-21.0']

def test_missing_history_is_not_success():
    with pytest.raises(ValueError):
        m.monthly_releases(b'<r><Prefix>release/2026-10-21.0/</Prefix></r>')

def test_distances():
    assert m.distance_miles(41, -73, 41, -73) == 0
    assert 68 < m.distance_miles(41, -73, 42, -73) < 70

def test_corrupt_resume_is_rejected(tmp_path):
    path = tmp_path/'P01.json'
    path.write_bytes(b'[]')
    path.with_suffix('.manifest.json').write_text(json.dumps({'sha256': hashlib.sha256(b'[]').hexdigest()}))
    assert m.valid_capture(path)
    path.write_bytes(b'corrupt')
    assert not m.valid_capture(path)

def test_real_regal_closure_capture():
    fixture_path = Path(__file__).parent/'fixtures/real/overture/regal-status-change.json'
    fixture = json.loads(fixture_path.read_text())
    assert fixture['before']['id'] == fixture['after']['id']
    assert fixture['before']['operating_status'] == 'open'
    assert fixture['after']['operating_status'] == 'permanently_closed'
    assert fixture['releases'] == ['2026-09-23.1', '2026-10-21.0']
