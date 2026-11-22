from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view, throttle_classes
from apps.accounts.permissions import ExpensiveThrottle
from rest_framework.response import Response
from apps.locations.models import Location
from apps.accounts.permissions import IsAdministrator
from apps.area.analysis import ensure_analysis
from .service import SECTIONS as AREA_SECTIONS, serialize


@api_view(['GET', 'POST'])
@throttle_classes([ExpensiveThrottle])
def area(request, location_id):
    location = get_object_or_404(Location.objects.select_related('current_revision'), pk=location_id)
    if request.method == 'POST':
        # Analyses run automatically (B3a). A member's POST only makes sure missing parts are queued;
        # an administrator's POST recomputes these sections.
        if location.current_revision is None or location.current_revision.lat is None:
            return Response({'detail': 'Place the pin before checking area data.'}, status=400)
        job = ensure_analysis(location.pk, list(AREA_SECTIONS) if IsAdministrator().has_permission(request, None) else None,
            requested_by=request.user)
        if job is None:
            return Response({'status': 'complete'})
        return Response({'job_id': str(job.pk), 'status': job.status}, status=202)
    return Response(serialize(location))


@api_view(['GET'])
def analysis_bundle(request, location_id):
    """PART C analysis bundle (B3b); opening it queues whatever is missing."""
    from .bundle import build
    location = get_object_or_404(Location.objects.select_related('current_revision', 'metrics_snapshot'), pk=location_id)
    return Response(build(location, user=request.user))
