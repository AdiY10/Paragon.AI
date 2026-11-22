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


def _analysis_row(location):
    """One entry of GET /api/analyses/ (redesign B5)."""
    from apps.area import analysis
    from .screens import expires_at
    placed = location.current_revision_id and location.current_revision.lat is not None
    if not placed:
        state = 'unplaced'
    elif not analysis.missing_sections(location):
        state = 'complete'
    elif analysis._attempts(location).filter(status__in=analysis.LIVE).exists():
        state = 'running'
    else:
        state = 'partial'
    expiry = expires_at(location)
    rev = location.current_revision
    return {'id': str(location.pk), 'name': location.name, 'display_label': location.name, 'address': location.address,
        'lat': rev.lat if rev else None, 'lon': rev.lon if rev else None, 'created_at': location.created_at.isoformat(),
        'kept': location.kept_at is not None, 'expires_at': expiry.isoformat() if expiry else None, 'state': state,
        'key_numbers': _key_numbers(location)}


def _key_numbers(location):
    from apps.locations.serializers import LocationSerializer
    return LocationSerializer().get_key_numbers(location)


@api_view(['GET', 'POST'])
@throttle_classes([ExpensiveThrottle])
def analyses(request):
    """Analyze a new place (redesign B5, PART C). POST {address, name?} or {lat, lon, label?}; GET recent."""
    from apps.locations.serializers import LocationSerializer
    from apps.locations.geocoding import lookup_payload
    from .screens import create_screen, create_point_screen, expire_screens, too_busy, OutsideUS
    if request.method == 'GET':
        expire_screens()
        recent = (Location.objects.filter(screening=True).exclude(status='archived')
            .select_related('current_revision', 'metrics_snapshot').order_by('-created_at')[:25])
        return Response([_analysis_row(l) for l in recent])
    if too_busy():
        return Response({'detail': 'Several analyses are running. Try again in a minute.', 'retry_after': 30},
            status=429, headers={'Retry-After': '30'})
    data = request.data
    if data.get('lat') is not None or data.get('lon') is not None:
        try:
            lat, lon = float(data.get('lat')), float(data.get('lon'))
        except (TypeError, ValueError):
            return Response({'detail': 'lat and lon must be numbers.'}, status=400)
        try:
            location, job = create_point_screen(lat=lat, lon=lon, label=str(data.get('label', '')).strip()[:200],
                actor=request.user)
        except OutsideUS as exc:
            return Response({'detail': str(exc)}, status=400)
        return Response({'location': LocationSerializer(location).data, 'geocode': {'status': 'map_point'},
            'analysis': {'state': 'queued', 'job_id': str(job.pk) if job else None}}, status=201)
    address = str(data.get('address', '')).strip()
    if not address or len(address) > 500:
        return Response({'detail': 'Enter a US street address or choose a point on the map.'}, status=400)
    location, lookup, status, jobs = create_screen(address=address, name=str(data.get('name', '')).strip()[:200],
        actor=request.user)
    body = {'location': LocationSerializer(location).data}
    if jobs:
        body.update(geocode={'status': 'matched', 'matched_address': location.current_revision.matched_address},
            analysis={'state': 'queued', 'job_id': jobs[0]})
        return Response(body, status=201)
    if lookup is not None and lookup.status in ('matched', 'ambiguous') and lookup.candidates:
        p = lookup_payload(lookup)
        body['geocode'] = {'status': 'ambiguous', 'lookup_id': p['id'], 'expected_version': p['expected_version'],
            'candidates': [{'index': i, 'matched_address': c.get('matched_address'), 'lat': c.get('lat'), 'lon': c.get('lon')}
                for i, c in enumerate(lookup.candidates)]}
        return Response(body)
    unavailable = status.startswith('geocoder_')
    body.update(geocode={'status': 'unavailable' if unavailable else 'no_match'}, next='place_pin')
    return Response(body, status=503 if unavailable else 200)


@api_view(['POST'])
def analysis_keep(request, location_id):
    """Star (keep) or unstar a new-place analysis: {kept: bool} -> {kept, expires_at}."""
    from .screens import keep_screen, expires_at
    location = get_object_or_404(Location, pk=location_id, screening=True)
    if not isinstance(request.data.get('kept'), bool):
        return Response({'detail': 'kept must be true or false.'}, status=400)
    location = keep_screen(location, request.data['kept'])
    expiry = expires_at(location)
    return Response({'kept': location.kept_at is not None, 'expires_at': expiry.isoformat() if expiry else None})
