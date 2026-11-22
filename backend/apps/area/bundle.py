"""GET /api/locations/<id>/analysis/ (redesign B3b, PART C): everything the analysis page needs.

One request: the location, the analysis state and job, every section with its own status, alerts,
risk badges, tenants and sources. A GET for a placed location with missing sections and no live job
queues the analysis (idempotent), so opening a page is enough to start it.
"""
from datetime import timedelta
from django.utils import timezone
from apps.operations.models import JobRun
from . import analysis
from .models import AreaSection

FAST_POLL_MS, SLOW_POLL_MS, FAST_POLL_FOR = 1500, 3000, timedelta(seconds=30)


def _job_payload(job):
    if job is None:
        return None
    attempt = job.dedup_key.rsplit(':', 1)[-1]
    return {'id': str(job.pk), 'status': job.status, 'kind': job.kind,
        'started_at': job.started_at.isoformat() if job.started_at else None,
        'attempt': int(attempt) if attempt.isdigit() else 1}


def _sources(*lists):
    seen, out = set(), []
    for items in lists:
        for s in items or []:
            key = (s.get('id'), s.get('period'))
            if key not in seen:
                seen.add(key)
                out.append(s)
    return out


def build(location, *, user=None, now=None, trigger=True):
    from apps.demographics.service import current_result, serialize as serialize_demographics
    from apps.insights.signals import active_for, risk_badges
    from apps.insights.screens import SCREEN_TTL_DAYS
    from apps.locations.serializers import LocationSerializer
    now = now or timezone.now()
    placed = analysis._placed(location)
    missing = analysis.missing_sections(location) if placed else list(analysis.ORDER)
    attempts = analysis._attempts(location) if placed else JobRun.objects.none()
    job = attempts.filter(status__in=analysis.LIVE).order_by('-created_at').first()
    if trigger and placed and missing and job is None and location.status != 'archived':
        job = analysis.ensure_analysis(location.pk, requested_by=user)
    last = attempts.filter(status__in=analysis.FINISHED).order_by('-finished_at').first()
    last_detail = (last.detail or {}) if last else {}
    job_sections = set((job.parameters or {}).get('sections') or []) if job else set()

    rows = {}
    for row in AreaSection.objects.filter(location=location, analysis_version=location.analysis_version).order_by(
            'section', '-computed_at'):
        rows.setdefault(row.section, row)

    def run_state(name):
        if job is not None and name in job_sections:
            return 'running' if job.status == JobRun.Status.RUNNING else 'pending'
        if not placed:
            return 'unavailable', 'NOT_PROVIDED'
        reason = last_detail.get(name) or 'NOT_COMPUTED'
        return ('pending', reason) if reason == 'INGESTING' else ('unavailable', reason)

    sections = {}
    demo = current_result(location) if placed else None
    if demo is not None and 'demographics' not in missing:
        payload = serialize_demographics(location, demo)
        three = next((r for r in demo.rings if r.get('radius_miles') == 3), demo.rings[0] if demo.rings else {})
        trends = (three.get('trends') or {})
        trend_reason = trends.get('reason') if isinstance(trends, dict) else None
        sections['demographics'] = {'status': 'ready', 'reason': None,
            'trends': 'unavailable' if trend_reason or not trends else 'ready',
            'computed_at': demo.computed_at.isoformat(), 'data': payload, 'sources': payload.get('sources', [])}
    for name in analysis.ORDER:
        if name in sections:
            continue
        row = rows.get(name)
        if row is not None and name not in missing:
            reason = None if row.status == 'available' else (row.data or {}).get('reason', 'UNAVAILABLE')
            sections[name] = {'status': 'ready' if row.status == 'available' else 'unavailable', 'reason': reason,
                'stale': any(s.get('stale') for s in row.sources or []), 'computed_at': row.computed_at.isoformat(),
                'data': row.data, 'sources': row.sources}
            continue
        state = run_state(name)
        status, reason = (state, None) if isinstance(state, str) else state
        # A previous version's result is not shown: the pin or rings changed since.
        sections[name] = {'status': status, 'reason': reason, 'stale': False, 'computed_at': None, 'data': None,
            'sources': []}
        if name == 'demographics':
            sections[name]['trends'] = status if status != 'unavailable' else 'unavailable'
    sections = {n: sections[n] for n in analysis.ORDER}

    ready = sum(1 for s in sections.values() if s['computed_at'])  # sections with a current result
    if not placed:
        state = 'unplaced'
    elif not missing:
        state = 'complete'
    elif job is not None:
        state = 'partial' if ready else ('running' if job.status == JobRun.Status.RUNNING else 'queued')
    else:
        state = 'partial' if ready else 'failed'
    poll = None
    if state in ('queued', 'running', 'partial') and job is not None:
        since = job.started_at or job.created_at
        poll = FAST_POLL_MS if now - since < FAST_POLL_FOR else SLOW_POLL_MS
    next_retry = None
    if state in ('failed', 'partial') and job is None and last is not None and last.finished_at:
        n = attempts.filter(status__in=analysis.FINISHED).count()
        next_retry = (last.finished_at + analysis.BACKOFF[min(n, len(analysis.BACKOFF) - 1)]).isoformat()

    loc = LocationSerializer(location).data
    screening = bool(getattr(location, 'screening', False))
    kept_at = getattr(location, 'kept_at', None)
    loc.update(kind='place' if screening else 'property', display_label=location.name,
        kept=bool(kept_at) if screening else None,
        expires_at=(location.created_at + timedelta(days=SCREEN_TTL_DAYS)).isoformat()
            if screening and not kept_at else None,
        lat=location.current_revision.lat if placed else None, lon=location.current_revision.lon if placed else None)

    tenants = []
    if location.status == 'owned':
        from apps.insights.tenant_views import _payload
        tenants = [_payload(t) for t in location.tenants.select_related('sec_filer').filter(archived=False)
            .order_by('-is_anchor', 'name')]
    return {
        'location': loc,
        'analysis': {'state': state, 'analysis_version': location.analysis_version, 'job': _job_payload(job),
            'next_retry_at': next_retry, 'poll_after_ms': poll},
        'sections': sections,
        'kpis': [], 'takeaways': [],  # B6b
        'signals': [] if screening else active_for(location),
        'risk_badges': risk_badges(location) if placed else [],
        'tenants': tenants,
        'sources': _sources(*(s.get('sources') for s in sections.values())),
    }
