"""The This Week brief (FR-21; docs/04 §5.4).

A brief is an immutable snapshot of what changed since the previous brief:
new or changed signals on owned properties, still-active High signals, and which
sources published new periods. "No material changes" is a valid, honest outcome.
"""
from django.db import transaction
from django.utils import timezone
from apps.sources.models import SourceSnapshot, SourceDefinition
from .models import Brief, Signal
from .signals import serialize, rank_key


def _sources_updated(since):
    """Latest data period per source among snapshots published since the previous brief."""
    qs = SourceSnapshot.objects.all()
    if since:
        qs = qs.filter(published_at__gt=since)
    latest = {}
    for snap in qs.order_by('published_at'):
        latest[snap.source_id] = snap
    names = dict(SourceDefinition.objects.values_list('id', 'name'))
    return [{'id': sid, 'name': names.get(sid, sid), 'period': s.data_period, 'release': s.release,
        'published_at': s.published_at.isoformat()} for sid, s in sorted(latest.items())]


@transaction.atomic
def generate(*, kind='weekly', now=None):
    now = now or timezone.now()
    previous = Brief.objects.order_by('-generated_at').first()
    since = previous.generated_at if previous else None
    baseline = previous is None
    active = (Signal.objects.filter(status='active', location__status='owned').select_related('location'))
    items = []
    for s in sorted(active, key=rank_key):
        new = baseline or s.first_detected_at > since
        changed = not new and s.last_changed_at > since
        still_high = s.severity == 'High' and not new and not changed
        if new or changed or still_high:
            items.append({**serialize(s), 'flag': 'new' if new else 'changed' if changed else 'still_active'})
    main = [i for i in items if i['severity'] in ('High', 'Watch')]
    fyi = [i for i in items if i['severity'] == 'FYI']
    properties = len({i['location']['id'] for i in main})
    owned = active.values('location').distinct().count()
    if baseline:
        title = 'Baseline: current conditions'
    elif main:
        n = len(main)
        title = (f"{n} item{'s' if n != 1 else ''} need{'s' if n == 1 else ''} attention across "
            f"{properties} propert{'ies' if properties != 1 else 'y'}")
    else:
        title = 'No material changes this week'
    return Brief.objects.create(kind='baseline' if baseline else kind, title=title, since=since,
        items=main, fyi=fyi, sources_updated=_sources_updated(since),
        stats={'attention_items': len(main), 'fyi_items': len(fyi), 'properties_with_items': properties,
            'properties_with_active_signals': owned})


def serialize_brief(b):
    return {'id': str(b.id), 'kind': b.kind, 'title': b.title, 'generated_at': b.generated_at.isoformat(),
        'since': b.since.isoformat() if b.since else None, 'items': b.items, 'fyi': b.fyi,
        'sources_updated': b.sources_updated, 'stats': b.stats}
