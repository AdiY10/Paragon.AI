"""Redesign B3b: parallel analysis waves and the analysis bundle endpoint (PART C)."""
import threading
import time
import pytest
from django.utils import timezone
from apps.area import analysis
from apps.operations.models import JobRun
from backend.tests.test_signals import placed, section

pytestmark = pytest.mark.django_db


def member(client, role='member'):
    from django.contrib.auth import get_user_model
    from apps.accounts.models import Membership
    user = get_user_model().objects.create_user(username=f'{role}@example.org', email=f'{role}@example.org')
    Membership.objects.create(email=f'{role}@example.org', user=user, role=role)
    client.force_login(user)
    return user


# ---- parallel waves ---------------------------------------------------------------

def test_parallel_run_starts_geography_sections_only_after_the_prefetch(monkeypatch):
    events, lock = [], threading.Lock()

    def note(what):
        with lock:
            events.append(what)

    def fake_section(name, *a):
        note(('start', name, threading.current_thread().name))
        time.sleep(0.05)
        note(('end', name))
        return 'available' if name != 'traffic' else 'HTTP_ERROR'

    def fake_prefetch(*a):
        note(('start', 'geo', threading.current_thread().name))
        time.sleep(0.1)
        note(('end', 'geo'))
    monkeypatch.setattr(analysis, '_run_section', fake_section)
    monkeypatch.setattr(analysis, '_prefetch_geographies', fake_prefetch)
    monkeypatch.setattr('apps.insights.signals.safe_evaluate', lambda pk: note(('evaluate',)))
    checks = []
    out = analysis.run_analysis('loc', 1, analysis.ORDER, parallel=True, check=lambda: checks.append(1))
    assert out == {'hazards': 'available', 'traffic': 'HTTP_ERROR', 'economy': 'available', 'businesses': 'available',
        'jobs': 'available', 'demographics': 'available'}
    geo_end = events.index(('end', 'geo'))
    for name in ('demographics', 'jobs'):
        assert next(i for i, e in enumerate(events) if e[:2] == ('start', name)) > geo_end
    starts = [e for e in events if e[0] == 'start']
    assert len({e[2] for e in starts}) > 1 and all(e[2].startswith('analysis') for e in starts)  # worker threads
    assert events[-1] == ('evaluate',) and checks  # alerts once, at the end; heartbeat between completions


def test_parallel_run_reports_stale(monkeypatch):
    def fake_section(name, *a):
        if name == 'economy':
            raise analysis.Stale()
        return 'available'
    monkeypatch.setattr(analysis, '_run_section', fake_section)
    monkeypatch.setattr(analysis, '_prefetch_geographies', lambda *a: None)
    with pytest.raises(analysis.Stale):
        analysis.run_analysis('loc', 1, ['hazards', 'economy'], parallel=True)


# ---- bundle ------------------------------------------------------------------------

def test_bundle_for_an_unplaced_property(client):
    from apps.locations.service import create_location
    member(client)
    loc = create_location(name='No pin', address='1 Main', actor=None, status='owned')
    body = client.get(f'/api/locations/{loc.pk}/analysis/').json()
    assert body['analysis'] == {'state': 'unplaced', 'analysis_version': loc.analysis_version, 'job': None,
        'next_retry_at': None, 'poll_after_ms': None}
    assert {s['status'] for s in body['sections'].values()} == {'unavailable'}
    assert body['location']['kind'] == 'property' and not JobRun.objects.exists()


def test_opening_the_bundle_queues_the_analysis_and_polls(client):
    member(client)
    loc = placed()
    body = client.get(f'/api/locations/{loc.pk}/analysis/').json()
    assert body['analysis']['state'] == 'queued' and body['analysis']['poll_after_ms'] == 1500
    assert body['analysis']['job']['attempt'] == 1 and list(body['sections']) == list(analysis.ORDER)
    assert {s['status'] for s in body['sections'].values()} == {'pending'}
    again = client.get(f'/api/locations/{loc.pk}/analysis/').json()
    assert again['analysis']['job']['id'] == body['analysis']['job']['id'] and JobRun.objects.count() == 1


def test_partial_then_complete(client, monkeypatch):
    member(client)
    loc = placed()
    job = analysis.ensure_analysis(loc.pk)
    JobRun.objects.filter(pk=job.pk).update(status='running', started_at=timezone.now() - __import__('datetime').timedelta(minutes=2))
    section(loc, 'hazards', {'flood_at_pin': {'zone': 'AE', 'sfha': True, 'in_sfha': True, 'bfe_ft': 9.0},
        'flood_nearby': {}, 'nri': {}})
    section(loc, 'traffic', {'reason': 'NOT_COVERED'}, status='unavailable')
    body = client.get(f'/api/locations/{loc.pk}/analysis/').json()
    a, s = body['analysis'], body['sections']
    assert a['state'] == 'partial' and a['poll_after_ms'] == 3000  # running for over 30 s
    assert s['hazards']['status'] == 'ready' and s['traffic'] == {**s['traffic'], 'status': 'unavailable', 'reason': 'NOT_COVERED'}
    assert s['economy']['status'] == 'running'
    assert body['risk_badges'][0]['level'] == 'inside'
    monkeypatch.setattr(analysis, 'missing_sections', lambda l: [])
    monkeypatch.setattr('apps.demographics.service.current_result', lambda l: None)
    JobRun.objects.filter(pk=job.pk).update(status='succeeded', finished_at=timezone.now())
    done = client.get(f'/api/locations/{loc.pk}/analysis/').json()['analysis']
    assert done['state'] == 'complete' and done['poll_after_ms'] is None and done['job'] is None


def test_failed_shows_reason_and_next_retry(client):
    member(client)
    loc = placed()
    now = timezone.now()
    for _ in range(3):  # three failures today: no new attempt until the window passes
        job = analysis.ensure_analysis(loc.pk)
        JobRun.objects.filter(pk=job.pk).update(status='failed', finished_at=now, detail={'traffic': 'HTTP_ERROR'})
    body = client.get(f'/api/locations/{loc.pk}/analysis/').json()
    assert body['analysis']['state'] == 'failed' and body['analysis']['job'] is None
    assert body['analysis']['next_retry_at'] is not None
    assert body['sections']['traffic'] == {**body['sections']['traffic'], 'status': 'unavailable', 'reason': 'HTTP_ERROR'}


def test_bundle_requires_sign_in(client):
    loc = placed()
    assert client.get(f'/api/locations/{loc.pk}/analysis/').status_code == 403
