from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view
from rest_framework.response import Response
from apps.locations.models import Location
from apps.operations.service import enqueue_job
from .service import serialize


@api_view(['GET', 'POST'])
def area(request, location_id):
    location = get_object_or_404(Location.objects.select_related('current_revision'), pk=location_id)
    if request.method == 'POST':
        if location.current_revision is None or location.current_revision.lat is None:
            return Response({'detail': 'Place the pin before checking area data.'}, status=400)
        job, created = enqueue_job(kind='compute_area_profile', scope=f'location:{location.pk}',
            dedup_key=f'area-profile:{location.pk}:{location.analysis_version}',
            parameters={'location_id': str(location.pk), 'analysis_version': location.analysis_version},
            requested_by=request.user)
        return Response({'job_id': str(job.pk), 'status': job.status, 'created': created}, status=202)
    return Response(serialize(location))
