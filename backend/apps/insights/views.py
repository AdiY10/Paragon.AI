import uuid
from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from apps.accounts.permissions import IsAdministrator, ExpensiveThrottle
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
    from .signals import serialize, rank_key, group_signals
    qs = Signal.objects.select_related('location').exclude(location__status='archived').exclude(location__screening=True)
    status = request.query_params.get('status', 'active')
    if status == 'all':
        qs = qs.exclude(status='retired')  # outside the alert scope (B7a): never listed
    else:
        qs = qs.filter(status=status)
    if loc := request.query_params.get('location'):
        try:
            qs = qs.filter(location_id=uuid.UUID(loc))
        except ValueError:
            return Response({'detail': 'location must be a location id'}, status=400)
    ranked = sorted(qs, key=rank_key)[:500]
    # `groups` is the PART C shape (one entry per county figure or shared place); `results` stays for
    # the current pages until the new Alerts page lands.
    return Response({'groups': group_signals(ranked), 'results': [serialize(s) for s in ranked]})


@api_view(['POST'])
def signal_review(request, signal_id):
    """FR-23: mark a signal reviewed (kept active), dismissed (hidden unless it escalates) or reopened.

    Optional ``note`` and ``feedback`` ("useful" / "not_useful"). ``apply_to_group: true`` applies the
    review to every property's copy of a shared alert (a county figure or one nearby place; B7a).
    """
    from django.utils import timezone
    from .models import Signal
    from .signals import serialize
    signal = get_object_or_404(Signal.objects.select_related('location'), pk=signal_id)
    action = request.data.get('action')
    if action not in ('reviewed', 'dismissed', 'reopened', 'feedback'):
        return Response({'detail': 'action must be reviewed, dismissed, reopened or feedback'}, status=400)
    feedback = request.data.get('feedback', '')
    if feedback not in ('', 'useful', 'not_useful'):
        return Response({'detail': 'feedback must be useful or not_useful'}, status=400)
    targets = [signal]
    if request.data.get('apply_to_group') is True:
        from .signals import group_key
        key = group_key(signal)
        targets = [s for s in Signal.objects.select_related('location').filter(rule_id=signal.rule_id, subject=signal.subject)
            .exclude(location__status='archived').exclude(status='retired') if group_key(s) == key] or [signal]
    from .metrics import refresh_snapshot
    for target in targets:
        fields = ['reviewed_by', 'reviewed_at']
        target.reviewed_by, target.reviewed_at = request.user, timezone.now()
        if 'note' in request.data:
            target.review_note = str(request.data.get('note', ''))[:2000]
            fields.append('review_note')
        if feedback:
            target.feedback = feedback
            fields.append('feedback')
        if action == 'dismissed':
            target.status = 'dismissed'
            fields.append('status')
        elif action == 'reopened' and target.status == 'dismissed':
            target.status = 'active'
            fields.append('status')
        target.save(update_fields=fields)
        refresh_snapshot(target.location)
    signal.refresh_from_db()
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
@permission_classes([IsAdministrator])
def brief_generate(request):
    """Admin: generate a brief now (in addition to Monday 07:00 US Eastern)."""
    from .brief import generate, serialize_brief
    return Response(serialize_brief(generate(kind='manual')), status=201)


@api_view(['GET', 'POST'])
@throttle_classes([ExpensiveThrottle])
def screens(request):
    """GET recent unsaved screens; POST {address, name?} to screen a new address (FR-25)."""
    from apps.locations.serializers import LocationSerializer
    from .screens import create_screen, expire_screens
    if request.method == 'POST':
        address = str(request.data.get('address', '')).strip()
        if not address or len(address) > 500:
            return Response({'detail': 'Enter a US street address.'}, status=400)
        location, lookup, status, jobs = create_screen(address=address, name=str(request.data.get('name', '')).strip()[:200],
            actor=request.user)
        return Response({'location': LocationSerializer(location).data, 'geocode_status': status, 'jobs': jobs},
            status=201)
    expire_screens()
    recent = Location.objects.filter(screening=True).exclude(status='archived').select_related('current_revision')
    return Response({'results': LocationSerializer(recent.order_by('-created_at')[:25], many=True).data})


@api_view(['POST'])
def screen_save(request, location_id):
    from apps.locations.serializers import LocationSerializer
    from .screens import save_screen
    location = get_object_or_404(Location, pk=location_id)
    location = save_screen(location, request.user)
    return Response(LocationSerializer(location).data)


@api_view(['GET'])
def compare_view(request):
    from .screens import compare
    ids = [i for i in request.query_params.get('ids', '').split(',') if i]
    if not 2 <= len(ids) <= 4:
        return Response({'detail': 'Choose 2 to 4 locations to compare.'}, status=400)
    import uuid
    try:
        ids = [str(uuid.UUID(i)) for i in ids]
    except ValueError:
        return Response({'detail': 'Invalid location id.'}, status=400)
    return Response(compare(ids))
