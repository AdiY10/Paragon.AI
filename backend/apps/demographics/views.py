from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view, throttle_classes
from apps.accounts.permissions import ExpensiveThrottle
from rest_framework.response import Response
from apps.locations.models import Location
from apps.accounts.permissions import IsAdministrator
from apps.area.analysis import ensure_analysis
from .service import current_result, serialize


@api_view(['GET', 'POST'])
@throttle_classes([ExpensiveThrottle])
def demographics(request, location_id):
    location = get_object_or_404(Location.objects.select_related('current_revision'), pk=location_id)
    if request.method == 'POST':
        # Analyses run automatically (B3a). A member's POST only makes sure missing parts are queued;
        # an administrator's POST recomputes these sections.
        if location.current_revision is None or location.current_revision.lat is None:
            return Response({'detail': 'Place the pin before computing ring demographics.'}, status=400)
        job = ensure_analysis(location.pk, ['demographics'] if IsAdministrator().has_permission(request, None) else None,
            requested_by=request.user)
        if job is None:
            return Response({'status': 'complete'})
        return Response({'job_id': str(job.pk), 'status': job.status}, status=202)
    return Response(serialize(location, current_result(location)))
