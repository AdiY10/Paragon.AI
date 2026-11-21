import time
from django.conf import settings
from django.contrib.auth import logout
from django.contrib.auth.views import redirect_to_login
from django.http import JsonResponse
from .models import Membership


class ActiveMembershipMiddleware:
    """Revocation is checked in the database on every authenticated request."""
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.membership = None
        if request.user.is_authenticated:
            started = request.session.setdefault('signed_in_at', int(time.time()))
            if time.time() - started > settings.SESSION_ABSOLUTE_SECONDS:
                logout(request)
                if not request.path.startswith('/api/'):
                    return redirect_to_login(request.get_full_path())
                return JsonResponse({'detail': 'Your session expired. Please sign in again.'}, status=401)
            request.membership = Membership.objects.filter(user=request.user, active=True).first()
            if request.membership is None:
                logout(request)
                return JsonResponse({'detail': 'Access has been removed. Contact your administrator.'}, status=403)
        return self.get_response(request)
