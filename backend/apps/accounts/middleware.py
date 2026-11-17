from django.contrib.auth import logout
from django.http import JsonResponse
from .models import Membership


class ActiveMembershipMiddleware:
    """Revocation is checked in the database on every authenticated request."""
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.membership = None
        if request.user.is_authenticated:
            request.membership = Membership.objects.filter(user=request.user, active=True).first()
            if request.membership is None:
                logout(request)
                return JsonResponse({'detail': 'Access has been removed. Contact your administrator.'}, status=403)
        return self.get_response(request)
