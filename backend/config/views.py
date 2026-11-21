from django.conf import settings
from django.contrib.auth.decorators import login_not_required
from django.core.exceptions import ImproperlyConfigured
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.middleware.csrf import get_token
from django.views.decorators.cache import never_cache
from .frontend import frontend_assets
from rest_framework.decorators import api_view
from rest_framework.response import Response

@login_not_required
def health(request):
    return JsonResponse({'status': 'ok'})


@login_not_required
@never_cache
def health_ready(request):
    """Readiness: the database answers. Returns no details on failure."""
    from django.db import connection
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
    except Exception:
        return JsonResponse({'status': 'unavailable'}, status=503)
    return JsonResponse({'status': 'ok'})

@never_cache
def application(request):
    try:
        assets = frontend_assets()
    except ImproperlyConfigured:
        return HttpResponse('Workspace UI unavailable. The application build must be installed.', status=503)
    return render(request, 'application/index.html', {**assets, 'csrf_token': get_token(request), 'login_url':settings.LOGIN_URL})

@api_view(['GET'])
def session(request):
    return Response({'email': request.user.email, 'role': request.membership.role, 'csrfToken': get_token(request), 'logout_url':'/access/logout/' if settings.PASSWORD_ACCESS_ENABLED else '/accounts/logout/', 'map': {'tile_url': settings.MAP_TILE_URL or None}})
