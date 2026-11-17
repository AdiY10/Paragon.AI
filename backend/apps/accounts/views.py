from django.db import transaction
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from .models import Membership
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
    return Response({'id': str(member.id), 'email': member.email, 'role': member.role}, status=201)


@api_view(['DELETE'])
@permission_classes([IsAdministrator])
def remove_user(request, member_id):
    # Serialize administrator changes to prevent concurrent removals of the last admin.
    with transaction.atomic():
        list(Membership.objects.select_for_update().filter(role='admin').order_by('id'))
        member = Membership.objects.filter(pk=member_id, active=True).first()
        if member is None:
            return Response({'detail': 'Membership not found.'}, status=404)
        if member.role == 'admin' and Membership.objects.filter(role='admin', active=True).count() <= 1:
            return Response({'detail': 'The last administrator cannot be removed.'}, status=409)
        member.active = False
        member.save(update_fields=['active', 'updated_at'])
    return Response(status=204)
