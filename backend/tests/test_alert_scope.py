"""Redesign B7a: alerts are High/Watch for actionable changes, with a next step; the rest retires quietly."""
from datetime import timedelta
import importlib
import pytest
from django.utils import timezone
from apps.insights import signals as engine
from apps.insights.models import Signal
from backend.tests.test_signals import placed, section, economy, TODAY

pytestmark = pytest.mark.django_db


def make(loc, rule, subject, severity='Watch', status='active', changed=None):
    s = Signal.objects.create(location=loc, rule_id=rule, subject=subject, category='X', severity=severity,
        direction='negative', title=rule, why='', analysis_version=loc.analysis_version, status=status)
    Signal.objects.filter(pk=s.pk).update(last_changed_at=changed or timezone.now() - timedelta(days=30))  # auto_now_add
    s.refresh_from_db()
    return s


def test_open_alerts_outside_the_scope_retire_without_looking_resolved():
    loc = placed()
    section(loc, 'economy', economy(priv=0.05, retail=0.0, unemp=0.0, permits=0.4, units=100))
    old = timezone.now() - timedelta(days=30)
    permits = make(loc, 'SIG-07', 'county:36111:permits', 'FYI', changed=old)
    flood = make(loc, 'SIG-11', 'flood:sfha', 'High', changed=old)
    jobs_up = make(loc, 'SIG-03', 'county:36111:private_jobs', 'FYI', changed=old)
    dismissed = make(loc, 'SIG-10', 'place:x', 'FYI', status='dismissed', changed=old)
    engine.evaluate(loc, today=TODAY)
    for s in (permits, flood, jobs_up, dismissed):
        s.refresh_from_db()
        assert s.status == 'retired' and s.resolved_reason == 'outside the alert scope'
        assert abs((s.last_changed_at - old).total_seconds()) < 1  # never reported as a recent change
    assert Signal.objects.filter(status='active').count() == 0


def test_migration_retires_removed_rules_and_fyi():
    from django.apps import apps as django_apps
    mig = importlib.import_module('apps.insights.migrations.0009_alert_rescope')
    loc = placed()
    keep = make(loc, 'SIG-05', 'county:1:unemployment')
    gone = [make(loc, 'SIG-01', 'ring3:population'), make(loc, 'SIG-08', 'road:primary', 'FYI'),
        make(loc, 'SIG-11', 'flood:sfha', 'High', status='dismissed')]
    resolved = make(loc, 'SIG-06', 'ring3:jobs', status='resolved')
    mig.retire(django_apps, None)
    assert Signal.objects.get(pk=keep.pk).status == 'active'
    assert {Signal.objects.get(pk=s.pk).status for s in gone} == {'retired'}
    assert Signal.objects.get(pk=resolved.pk).status == 'resolved'


def road(change, prior=20_000, **kw):
    return {'roads': [{'label': 'Route 9', 'aadt': 18_000, 'year': 2025, 'prior_aadt': prior, 'prior_year': 2024,
        'change_pct': change, **kw}]}


@pytest.mark.parametrize('data,alert', [
    (road(-0.12), True),
    (road(-0.09), False),                      # below the 10% decline
    (road(0.15), False),                       # increases are context, not alerts
    (road(-0.20, prior=2_500), False),         # minor road
    (road(None, reason='SAME_COUNT'), False),  # the state carried the same count forward
])
def test_traffic_alerts_only_for_a_real_decline_on_a_main_road(data, alert):
    loc = placed()
    section(loc, 'traffic', data)
    engine.evaluate(loc, today=TODAY)
    got = list(Signal.objects.filter(rule_id='SIG-08').values_list('severity', flat=True))
    assert got == (['Watch'] if alert else [])


def closure(**kw):
    base = {'id': 'p1', 'name': 'Place', 'distance_mi': 0.3, 'evidence': 'marked permanently closed', 'category': 'restaurant'}
    return {'release': '2026-11-18.0', 'prior_release': '2026-10-21.0', 'changes': {'closures': [{**base, **kw}]}}


@pytest.mark.parametrize('data,severity', [
    (closure(name="Joe's Pizza"), None),                                          # not an anchor or grocer
    (closure(name='Stop & Shop', brand='Stop & Shop', category='supermarket', distance_mi=0.9), 'Watch'),
    (closure(name='Stop & Shop', brand='Stop & Shop', category='supermarket', distance_mi=1.2), None),
    (closure(name='Target', brand='Target', category='department_store', distance_mi=0.6), 'Watch'),
    (closure(name='Local Market', category='grocery_store', distance_mi=0.4), 'Watch'),
    (closure(name='Stop & Shop', brand='Stop & Shop', category='supermarket', confirmed=False), None),
])
def test_closure_alerts_are_anchors_and_grocers_within_a_mile(data, severity):
    loc = placed()
    section(loc, 'businesses', data)
    engine.evaluate(loc, today=TODAY)
    got = list(Signal.objects.filter(rule_id='SIG-09').values_list('severity', flat=True))
    assert got == ([severity] if severity else [])


def test_the_tenants_own_store_closing_is_high():
    from apps.locations.models import Tenant
    loc = placed()
    Tenant.objects.create(location=loc, name="Joe's Pizza", normalized_key='joes pizza', origin='user')
    section(loc, 'businesses', closure(name="Joe's Pizza", brand="Joe's Pizza", distance_mi=0.05))
    engine.evaluate(loc, today=TODAY)
    s = Signal.objects.get(rule_id='SIG-09')
    assert s.severity == 'High' and s.evidence['tenant_match'] is True and s.next_step


def test_a_previous_broad_closure_alert_retires_under_the_new_scope():
    loc = placed()
    section(loc, 'businesses', closure(name="Joe's Pizza"))
    old = make(loc, 'SIG-09', 'place:p1', 'Watch')
    engine.evaluate(loc, today=TODAY)
    old.refresh_from_db()
    assert old.status == 'retired'


def test_county_alert_is_one_group_and_a_review_can_cover_the_group(client):
    from django.contrib.auth import get_user_model
    from apps.accounts.models import Membership
    user = get_user_model().objects.create_user(username='m@example.org', email='m@example.org')
    Membership.objects.create(email='m@example.org', user=user, role='member')
    client.force_login(user)
    a, b = placed('A'), placed('B')
    for loc in (a, b):
        section(loc, 'economy', economy(priv=0.0, retail=0.0, permits=0.0, units=0))  # SIG-05 only
        engine.evaluate(loc, today=TODAY)
    body = client.get('/api/signals/').json()
    assert len(body['results']) == 2 and len(body['groups']) == 1
    group = body['groups'][0]
    assert group['rule_id'] == 'SIG-05' and {l['name'] for l in group['locations']} == {'A', 'B'}
    assert len(group['signal_ids']) == 2 and group['next_step']
    r = client.post(f"/api/signals/{group['signal_ids'][0]}/review/",
        {'action': 'dismissed', 'apply_to_group': True}, content_type='application/json')
    assert r.status_code == 200 and r.json()['status'] == 'dismissed'
    assert set(Signal.objects.values_list('status', flat=True)) == {'dismissed'}
    assert client.get('/api/signals/').json() == {'groups': [], 'results': []}


def test_retired_alerts_are_never_listed(client):
    from backend.tests.test_accounts import member
    user, _ = member()
    client.force_login(user)
    loc = placed()
    make(loc, 'SIG-07', 'county:1:permits', 'FYI', status='retired')
    assert client.get('/api/signals/?status=all').json()['results'] == []


def test_weekly_brief_schedule_stays_off():
    from apps.operations.models import JobSchedule
    from apps.operations.scheduler import sync_schedules
    sync_schedules(enable_available=True)
    assert JobSchedule.objects.get(name='brief_weekly').enabled is False
    assert JobSchedule.objects.get(name='sec_daily').enabled is True
