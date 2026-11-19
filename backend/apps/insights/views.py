from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view
from rest_framework.response import Response
from apps.locations.models import Location
from .metrics import summary


def _signals(location):
    try:
        from .signals import active_for
    except ImportError:
        return []
    return active_for(location)


@api_view(['GET'])
def location_summary(request, location_id):
    location = get_object_or_404(Location.objects.select_related('current_revision'), pk=location_id)
    signals = _signals(location)
    return Response({**summary(location, signals), 'signals': signals})


@api_view(['GET'])
def signal_list(request):
    """Portfolio-wide signals, ranked (docs/04 §5.4). ?status=active|resolved|all, ?location=<uuid>."""
    from .models import Signal
    from .signals import serialize, rank_key
    qs = Signal.objects.select_related('location').exclude(location__status='archived')
    status = request.query_params.get('status', 'active')
    if status != 'all':
        qs = qs.filter(status=status)
    if loc := request.query_params.get('location'):
        qs = qs.filter(location_id=loc)
    return Response({'results': [serialize(s) for s in sorted(qs, key=rank_key)][:500]})


@api_view(['POST'])
def signal_review(request, signal_id):
    """FR-23: mark a signal reviewed (kept active) or dismissed (hidden unless it escalates)."""
    from .models import Signal
    from .signals import serialize
    signal = get_object_or_404(Signal.objects.select_related('location'), pk=signal_id)
    action = request.data.get('action')
    if action not in ('reviewed', 'dismissed'):
        return Response({'detail': 'action must be reviewed or dismissed'}, status=400)
    note = str(request.data.get('note', ''))[:2000]
    signal.reviewed_by = request.user
    signal.review_note = note
    if action == 'dismissed':
        signal.status = 'dismissed'
    signal.save(update_fields=['reviewed_by', 'review_note', 'status'])
    return Response(serialize(signal))


@api_view(['GET'])
def brief_latest(request):
    from .models import Brief
    from .brief import serialize_brief
    latest = Brief.objects.order_by('-generated_at').first()
    history = [{'id': str(b.id), 'title': b.title, 'generated_at': b.generated_at.isoformat(), 'kind': b.kind}
        for b in Brief.objects.order_by('-generated_at')[:26]]
    return Response({'brief': serialize_brief(latest) if latest else None, 'history': history})


@api_view(['GET'])
def brief_detail(request, brief_id):
    from .models import Brief
    from .brief import serialize_brief
    return Response(serialize_brief(get_object_or_404(Brief, pk=brief_id)))


@api_view(['POST'])
def brief_generate(request):
    """Admin: generate a brief now (in addition to Monday 07:00 US Eastern)."""
    from apps.accounts.models import Membership
    from .brief import generate, serialize_brief
    if not Membership.objects.filter(user=request.user, role='admin').exists():
        return Response({'detail': 'Administrators only'}, status=403)
    return Response(serialize_brief(generate(kind='manual')), status=201)
