from django.db import transaction
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from .models import Membership, AccessAuditEvent
from .permissions import IsAdministrator

class InviteSerializer(serializers.Serializer):
    email = serializers.EmailField()
    role = serializers.ChoiceField(choices=Membership.Role.choices, default=Membership.Role.MEMBER)


@api_view(['GET', 'POST'])
@permission_classes([IsAdministrator])
def users(request):
    if request.method == 'GET':
        return Response([{'id': str(m.id), 'email': m.email, 'role': m.role, 'active': m.active}
            for m in Membership.objects.order_by('email')])
    serializer = InviteSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    email = serializer.validated_data['email'].strip().lower()
    with transaction.atomic():
        member, created = Membership.objects.get_or_create(email=email,
            defaults={'role': serializer.validated_data['role'], 'invited_by': request.user})
        if not created:
            return Response({'detail': 'This email already has an invitation or membership.'}, status=409)
        AccessAuditEvent.objects.create(actor=request.user, membership=member, action='invited',
            after={'email': member.email, 'role': member.role, 'active': member.active})
    return Response({'id': str(member.id), 'email': member.email, 'role': member.role}, status=201)


class RoleSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=Membership.Role.choices)


@api_view(['PATCH', 'DELETE'])
@permission_classes([IsAdministrator])
def member_detail(request, member_id):
    serializer = None
    if request.method == 'PATCH':
        serializer = RoleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
    with transaction.atomic():
        # All admin mutations acquire the same ordered locks. Pending invitations
        # cannot substitute for the final admin who has actually signed in.
        list(Membership.objects.select_for_update().filter(role='admin').order_by('id'))
        member = Membership.objects.select_for_update().filter(pk=member_id, active=True).first()
        if member is None:
            return Response({'detail': 'Membership not found.'}, status=404)
        removing_admin = member.role == 'admin' and (
            request.method == 'DELETE' or serializer.validated_data['role'] != 'admin')
        if removing_admin and member.user_id and Membership.objects.filter(
                role='admin', active=True, user__isnull=False).count() <= 1:
            return Response({'detail': 'The last signed-in administrator cannot be removed or demoted.'}, status=409)
        before = {'role': member.role, 'active': member.active}
        if request.method == 'DELETE':
            member.active = False
            action = 'removed'
        else:
            member.role = serializer.validated_data['role']
            action = 'role_changed'
        member.save(update_fields=['role', 'active', 'updated_at'])
        AccessAuditEvent.objects.create(actor=request.user, membership=member, action=action,
            before=before, after={'role': member.role, 'active': member.active})
    if request.method == 'DELETE':
        return Response(status=204)
    return Response({'id': str(member.id), 'role': member.role, 'active': member.active})


from rest_framework.decorators import api_view as _api_view, permission_classes as _perm
from rest_framework.response import Response as _Response
from .permissions import IsAdministrator as _IsAdministrator


@_api_view(['GET'])
@_perm([_IsAdministrator])
def access_log(request):
    """Admin: who is on the guest list, when each person was last active, and recent sign-ins."""
    from .models import AccessAuditEvent, Membership
    people = [{'email': m.email, 'role': m.role, 'active': m.active,
        'last_seen_at': m.last_seen_at.isoformat() if m.last_seen_at else None}
        for m in Membership.objects.order_by('-last_seen_at', 'email')]
    events = [{'email': e.membership.email, 'action': e.action, 'method': (e.after or {}).get('method'),
        'at': e.created_at.isoformat()}
        for e in AccessAuditEvent.objects.filter(action__in=['password_login', 'password_login_failed', 'logout'])
            .select_related('membership').order_by('-created_at')[:100]]
    return _Response({'people': people, 'events': events})
