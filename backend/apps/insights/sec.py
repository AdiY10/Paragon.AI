"""SEC EDGAR tenant watch (SRC-14; FR-22; SIG-12, SIG-13).

Company-level filings only: an 8-K item never says which stores are affected.
SEC fair access requires a declared User-Agent with a contact email, configured
as SEC_USER_AGENT; without it the daily job reports NOT_CONFIGURED instead of
calling EDGAR. Requests are throttled to at most 5 per second.
"""
from datetime import date, timedelta
import json
import os
import re
import time
from apps.area.http import fetch, SourceError

SUBMISSIONS = 'https://data.sec.gov/submissions/CIK{cik:0>10}.json'
SEARCH = 'https://efts.sec.gov/LATEST/search-index'
WATCHED = {'1.03': ('SIG-12', 'High', 'Bankruptcy or receivership'),
    '2.05': ('SIG-13', 'Watch', 'Costs associated with exit or disposal activities'),
    '2.06': ('SIG-13', 'Watch', 'Material impairments')}
HISTORY_YEARS = 5
SIGNAL_WINDOW_DAYS = 90
_last_call = [0.0]


def user_agent():
    ua = os.environ.get('SEC_USER_AGENT', '').strip()
    if not ua or '@' not in ua:
        raise SourceError('NOT_CONFIGURED', 'Set SEC_USER_AGENT="<App name> <contact email>"')
    return ua


def _throttle():
    wait = 0.2 - (time.monotonic() - _last_call[0])
    if wait > 0:
        time.sleep(wait)
    _last_call[0] = time.monotonic()


def fetch_submissions(cik, *, opener=None):
    _throttle()
    return fetch(SUBMISSIONS.format(cik=int(cik)), opener=opener, headers={'User-Agent': user_agent()},
        max_bytes=32 * 1024 * 1024)


def search_companies(query, *, opener=None):
    """EDGAR entity search for admin suggestions. Returns [{cik, name}] (never applied automatically)."""
    if not query or len(query) > 100:
        return []
    _throttle()
    raw = fetch(SEARCH, params={'keysTyped': query}, opener=opener, headers={'User-Agent': user_agent()})
    hits = json.loads(raw).get('hits', {}).get('hits', [])
    return [{'cik': h['_id'], 'name': h['_source'].get('entity')} for h in hits[:10] if str(h.get('_id', '')).isdigit()]


def parse_submissions(raw, *, today=None):
    """8-K filings with watched items in the last five years, newest first."""
    today = today or date.today()
    data = json.loads(raw)
    recent = data.get('filings', {}).get('recent', {})
    forms = recent.get('form') or []
    if not isinstance(forms, list):
        raise SourceError('SCHEMA_ERROR', 'unexpected EDGAR layout')
    cik = int(data.get('cik', 0) or 0)
    events = []
    for i, form in enumerate(forms):
        if not form.startswith('8-K'):
            continue
        filed = date.fromisoformat(recent['filingDate'][i])
        if filed < today - timedelta(days=365 * HISTORY_YEARS):
            continue
        items = [x.strip() for x in (recent['items'][i] or '').split(',') if x.strip()]
        watched = [x for x in items if x in WATCHED]
        if not watched:
            continue
        accession = recent['accessionNumber'][i]
        folder = accession.replace('-', '')
        events.append({'filed': filed.isoformat(), 'form': form, 'items': items, 'watched': watched,
            'accession': accession,
            'url': f'https://www.sec.gov/Archives/edgar/data/{cik}/{folder}/{recent["primaryDocument"][i]}',
            'index_url': f'https://www.sec.gov/Archives/edgar/data/{cik}/{folder}/'})
    events.sort(key=lambda e: e['filed'], reverse=True)
    return {'cik': str(cik), 'name': data.get('name'), 'events': events}


def _latest_events(cik):
    from apps.sources.models import SourceSnapshot
    from apps.sources.storage import LocalArtifactStore
    from django.conf import settings
    snap = SourceSnapshot.objects.filter(source_id='SRC-14', scope=f'sec:cik:{int(cik)}').order_by('-retrieved_at').first()
    if snap is None:
        return None, None
    with LocalArtifactStore(settings.SOURCE_ARTIFACT_ROOT).open_verified(snap.artifact_key) as handle:
        return parse_submissions(handle.read()), snap


def tenant_events(tenant):
    filer = getattr(tenant, 'sec_filer', None)
    if filer is None:
        return None
    parsed, snap = _latest_events(filer.cik)
    if parsed is None:
        return {'cik': filer.cik, 'company': filer.company_name, 'events': [], 'checked_at': None}
    return {'cik': filer.cik, 'company': filer.company_name, 'events': parsed['events'],
        'checked_at': snap.retrieved_at.isoformat()}


def tenant_candidates(location, *, today=None):
    """One SIG-12 / SIG-13 per tenant and rule when a mapped filer has watched 8-Ks within 90 days.

    Multiple filings (e.g. several bankruptcy 8-Ks) collapse into one signal citing
    the latest filing and the count, so the brief is not flooded with duplicates.
    """
    from .signals import _candidate
    today = today or date.today()
    out = []
    for tenant in location.tenants.filter(archived=False).select_related('sec_filer'):
        info = tenant_events(tenant)
        if not info:
            continue
        by_rule = {}
        for event in info['events']:
            filed = date.fromisoformat(event['filed'])
            if filed < today - timedelta(days=SIGNAL_WINDOW_DAYS):
                continue
            for item in event['watched']:
                rule = WATCHED[item][0]
                by_rule.setdefault(rule, []).append((event, item))
        for rule, hits in by_rule.items():
            event, item = max(hits, key=lambda h: h[0]['filed'])
            severity, label = WATCHED[item][1], WATCHED[item][2]
            filings = sorted({h[0]['accession']: h[0]['filed'] for h in hits}.items(), key=lambda kv: kv[1], reverse=True)
            why = ('The parent company of a tenant at this property reported a bankruptcy or receivership. Store '
                'closures and lease rejections are possible; this location may or may not be affected.'
                if rule == 'SIG-12' else
                'The company reported exit costs or impairments, which often accompany store closures. '
                'Company-level; check whether this location is affected.')
            more = f' ({len(filings)} filings in 90 days)' if len(filings) > 1 else ''
            out.append(_candidate(rule, f'sec:{tenant.pk}:{rule}', 'Tenant', severity, 'negative',
                f'{tenant.name}: {info["company"]} filed an 8-K (Item {item}, {label}) on {event["filed"]}{more}', why,
                {'tenant': tenant.name, 'cik': info['cik'], 'company': info['company'], 'items': event['items'],
                    'filing_url': event['url'], 'filing_index': event['index_url'], 'filed': event['filed'],
                    'filings_in_window': len(filings)},
                f'Filed {event["filed"]}', 'SRC-14', event_date=date.fromisoformat(event['filed'])))
    return out


def refresh_all(context=None, *, opener=None):
    """Daily: fetch submissions for every mapped filer, store snapshots, re-evaluate affected locations."""
    import io
    from apps.sources.snapshots import publish_snapshot, ValidationReport
    from apps.sources.storage import LocalArtifactStore
    from apps.area.service import note_check
    from django.conf import settings
    from .models import TenantFiler
    from .signals import safe_evaluate
    user_agent()  # NOT_CONFIGURED before any request
    store = LocalArtifactStore(settings.SOURCE_ARTIFACT_ROOT)
    ciks = sorted({f.cik for f in TenantFiler.objects.all()})
    fetched = failed = 0
    for cik in ciks:
        if context:
            context.heartbeat()
        scope = f'sec:cik:{int(cik)}'
        try:
            raw = fetch_submissions(cik, opener=opener)
            parsed = parse_submissions(raw)
            snap, _ = publish_snapshot(source_id='SRC-14', scope=scope, release=date.today().isoformat(),
                data_period=f'Filings through {date.today().isoformat()}', source_url=SUBMISSIONS.format(cik=int(cik)),
                adapter_version='sec-submissions-v1', stream=io.BytesIO(raw), store=store,
                validation=ValidationReport(True, True, {'format': 'EDGAR submissions JSON'}, len(parsed['events'])))
            note_check('SRC-14', scope, snapshot=snap)
            fetched += 1
        except SourceError as exc:
            note_check('SRC-14', scope, error=exc.code if exc.code != 'NOT_COVERED' else 'HTTP_ERROR')
            failed += 1
    location_ids = set(TenantFiler.objects.values_list('tenant__location_id', flat=True))
    for lid in location_ids:
        safe_evaluate(lid)
    return fetched, failed
