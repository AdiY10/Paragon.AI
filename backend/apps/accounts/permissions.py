from rest_framework.permissions import BasePermission
from rest_framework.throttling import UserRateThrottle


class IsAdministrator(BasePermission):
    message = 'Administrators only'

    def has_permission(self, request, view):
        member = getattr(request, 'membership', None)
        return bool(member and member.active and member.role == 'admin')


class ExpensiveThrottle(UserRateThrottle):
    """Per-user cap on actions that start external fetches or jobs (screen, compute, SEC search).

    Reads (GET) are never throttled; only writes and SEC search, which calls the SEC.
    """
    scope = 'expensive'

    def allow_request(self, request, view):
        if request.method == 'GET' and '/sec' not in request.path:
            return True
        return super().allow_request(request, view)
