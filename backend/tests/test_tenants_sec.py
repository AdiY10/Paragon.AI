"""T8/T9: tenant roster API, listing import, SEC filer mapping and tenant watch (FR-07, FR-22, SIG-12/13)."""
from datetime import date, datetime, timezone
import io
import uuid
from pathlib import Path
import pytest
from apps.area.http import SourceError
from apps.insights import sec
from apps.insights.models import Signal, TenantFiler
from apps.insights.signals import evaluate
from apps.locations.models import Tenant

pytestmark = pytest.mark.django_db
FIX = Path('tests/fixtures/real/area')
TODAY = date(2026, 11, 19)


def users(client):
    from django.contrib.auth import get_user_model
    from apps.accounts.models import Membership
    from apps.sources.catalog import sync_catalog
    sync_catalog()
    admin = get_user_model().objects.create_user(username='a@example.org', email='a@example.org')
    Membership.objects.create(email='a@example.org', user=admin, role='admin')
    client.force_login(admin)
    return admin


def owned(name='Southside Shopping Center'):
    from backend.tests.test_signals import placed
    return placed(name)


def publish_submissions(cik, tmp_path, settings):
    from apps.sources.snapshots import publish_snapshot, ValidationReport
    from apps.sources.storage import LocalArtifactStore
    settings.SOURCE_ARTIFACT_ROOT = tmp_path / 'artifacts'
    raw = (FIX / f'sec_submissions_CIK{int(cik):010d}.json').read_bytes()
    publish_snapshot(source_id='SRC-14', scope=f'sec:cik:{int(cik)}', release='2026-11-19', data_period='Filings',
        source_url=sec.SUBMISSIONS.format(cik=int(cik)), adapter_version='sec-submissions-v1', stream=io.BytesIO(raw),
        store=LocalArtifactStore(settings.SOURCE_ARTIFACT_ROOT), validation=ValidationReport(True, True, {'f': 1}, 1),
        retrieved_at=datetime(2026, 11, 19, tzinfo=timezone.utc))


def test_listing_parser_on_real_seed_text():
    from apps.insights.management.commands.import_listing_tenants import parse_listing
    southside = parse_listing("Rite Aid (anchor); Dollar Tree (anchor); Popeyes; McDonald's")
    assert southside[0] == {'name': 'Rite Aid', 'is_anchor': True, 'presence': 'listed_unverified', 'qualifier': 'anchor'}
    assert southside[2]['is_anchor'] is None
    symmes = parse_listing("US Bank; Take 5 Oil and Jersey Mike's (listed as soon to open)")
    assert [(t['name'], t['presence']) for t in symmes[1:]] == [('Take 5 Oil', 'planned_unverified'), ("Jersey Mike's", 'planned_unverified')]
    cypress = parse_listing("Costco; TJ Maxx (listing says 'Join', so these may be co-tenants or neighbors)")
    assert {t['presence'] for t in cypress} == {'neighbor_or_cotenant'}


def test_import_listing_tenants_is_idempotent_and_unconfirmed():
    from django.core.management import call_command
    from apps.locations.seeding import import_public_portfolio
    from apps.sources.catalog import sync_catalog
    sync_catalog()
    import_public_portfolio()
    call_command('import_listing_tenants')
    n = Tenant.objects.count()
    call_command('import_listing_tenants')
    assert Tenant.objects.count() == n > 60
    rite = Tenant.objects.get(location__seed_id='P35', name='Rite Aid')
    assert rite.is_anchor is True and rite.confirmed is False and rite.presence == 'listed_unverified'


def test_submissions_parser_real_rite_aid_and_leslies():
    rite = sec.parse_submissions((FIX / 'sec_submissions_CIK0000084129.json').read_bytes(), today=TODAY)
    filed = {e['filed']: e for e in rite['events']}
    assert '1.03' in filed['2023-10-16']['watched'] and filed['2023-10-16']['url'].startswith('https://www.sec.gov/Archives/edgar/data/84129/')
    leslies = sec.parse_submissions((FIX / 'sec_submissions_CIK0001821806.json').read_bytes(), today=TODAY)
    assert [e['filed'] for e in leslies['events'][:3]] == ['2026-10-22', '2026-10-05', '2026-09-30']
    assert all('1.03' in e['watched'] for e in leslies['events'][:3])


def test_sec_requires_contact_user_agent(monkeypatch):
    monkeypatch.delenv('SEC_USER_AGENT', raising=False)
    with pytest.raises(SourceError) as exc:
        sec.refresh_all()
    assert exc.value.code == 'NOT_CONFIGURED'
    monkeypatch.setenv('SEC_USER_AGENT', 'ParagonRadar no-email')
    with pytest.raises(SourceError):
        sec.user_agent()


def test_recent_bankruptcy_raises_high_signal_old_one_is_past_event(client, tmp_path, settings):
    admin = users(client)
    loc = owned()
    leslie = Tenant.objects.create(location=loc, name="Leslie's", normalized_key='x1', origin='user')
    rite = Tenant.objects.create(location=loc, name='Rite Aid', normalized_key='x2', origin='user', is_anchor=True)
    publish_submissions(1821806, tmp_path, settings)
    publish_submissions(84129, tmp_path, settings)
    TenantFiler.objects.create(tenant=leslie, cik='1821806', company_name="Leslie's, Inc.", mapped_by=admin)
    TenantFiler.objects.create(tenant=rite, cik='84129', company_name='NEW RITE AID, LLC', mapped_by=admin)
    evaluate(loc, today=TODAY)
    s12 = Signal.objects.get(rule_id='SIG-12')  # three bankruptcy 8-Ks collapse into one signal
    assert s12.severity == 'High' and "Leslie's" in s12.title and s12.evidence['filing_url'].startswith('https://www.sec.gov/')
    assert s12.evidence['filed'] == '2026-10-22' and s12.evidence['filings_in_window'] == 3
    assert Signal.objects.get(rule_id='SIG-13').severity == 'Watch'  # 2.05 / 2.06 on 2026-09-30
    assert not Signal.objects.filter(title__contains='RITE AID').exists()
    rows = client.get(f'/api/locations/{loc.pk}/tenants/').json()['results']
    rite_row = next(r for r in rows if r['name'] == 'Rite Aid')
    assert any(e['filed'] == '2023-10-16' for e in rite_row['sec']['events'])


def test_tenant_api_create_confirm_archive_and_admin_mapping(client, monkeypatch):
    admin = users(client)
    loc = owned()
    url = f'/api/locations/{loc.pk}/tenants/'
    made = client.post(url, {'name': 'CVS Pharmacy', 'is_anchor': True}, content_type='application/json').json()
    assert made['name'] == 'CVS Pharmacy' and made['confirmed'] is False
    dup = client.post(url, {'name': 'cvs pharmacy'}, content_type='application/json')
    assert dup.status_code == 409
    done = client.post(f"{url}{made['id']}/confirm/", {'expected_version': made['version']}, content_type='application/json').json()
    assert done['confirmed'] is True
    gone = client.patch(f"{url}{made['id']}/", {'expected_version': done['version'], 'archived': True}, content_type='application/json').json()
    assert gone['archived'] is True and gone['confirmed'] is False
    mapped = client.post(f"{url}{made['id']}/sec/", {'cik': '64803', 'company_name': 'CVS HEALTH Corp'}, content_type='application/json')
    assert mapped.status_code == 201 and mapped.json()['sec']['cik'] == '64803'
    monkeypatch.delenv('SEC_USER_AGENT', raising=False)
    assert client.get('/api/sec/search/?q=cvs').json()['error'] == 'NOT_CONFIGURED'


def test_entity_search_parser(monkeypatch):
    monkeypatch.setenv('SEC_USER_AGENT', 'ParagonRadar admin@example.org')

    class Opener:
        def open(self, request, timeout=None):
            assert request.get_header('User-agent') == 'ParagonRadar admin@example.org'
            return io.BytesIO((FIX / 'sec_entity_search_rite_aid.json').read_bytes())
    hits = sec.search_companies('rite aid', opener=Opener())
    assert hits[0] == {'cik': '84129', 'name': 'NEW RITE AID, LLC'}


# ---- R2 item 10 ---------------------------------------------------------------------------

def test_tenant_edit_keeps_sections_valid_and_escalates_own_store_closure(client):
    from backend.tests.test_signals import section
    from apps.area.models import AreaSection
    from apps.insights import signals as engine
    users(client)
    loc = owned()
    section(loc, 'businesses', {'release': '2026-11-18.0', 'changes': {'closures': [{'id': 'p1', 'name': 'CVS Pharmacy',
        'brand': 'CVS Pharmacy', 'severity': 'Watch', 'distance_mi': 0.05, 'evidence': 'marked permanently closed'}]}})
    engine.evaluate(loc)
    assert Signal.objects.get(rule_id='SIG-09').severity == 'Watch'
    version = loc.analysis_version
    url = f'/api/locations/{loc.pk}/tenants/'
    assert client.post(url, {'name': 'CVS Pharmacy'}, content_type='application/json').status_code == 200
    loc.refresh_from_db()
    assert loc.analysis_version == version and AreaSection.objects.filter(location=loc, analysis_version=version).exists()
    s = Signal.objects.get(rule_id='SIG-09')
    assert s.severity == 'High' and 'tenant' in s.why


def test_filer_mapping_applies_to_the_same_brand_at_other_properties(client):
    from apps.locations import tenants as svc
    from apps.insights.models import TenantFiler
    admin = users(client)
    a, b = owned('Center A'), owned('Center B')
    ta, _ = svc.create_tenant(location_id=a.pk, name='Rite Aid', request_key=uuid.uuid4(), actor=admin)
    tb, _ = svc.create_tenant(location_id=b.pk, name='RITE AID', request_key=uuid.uuid4(), actor=admin)
    r = client.post(f'/api/locations/{a.pk}/tenants/{ta.pk}/sec/', {'cik': '84129', 'company_name': 'RITE AID CORP'},
        content_type='application/json')
    assert r.status_code == 201
    assert set(TenantFiler.objects.values_list('tenant_id', flat=True)) == {ta.pk, tb.pk}
