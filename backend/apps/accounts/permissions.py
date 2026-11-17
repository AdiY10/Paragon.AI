from rest_framework.permissions import BasePermission

class IsAdministrator(BasePermission):
    def has_permission(self, request, view):
        member = getattr(request, 'membership', None)
        return bool(member and member.active and member.role == 'admin')
