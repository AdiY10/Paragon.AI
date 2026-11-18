from django.core.exceptions import ValidationError
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from .models import Location
from .serializers import LocationSerializer,CreateSerializer,UpdateSerializer,PinSerializer,ConfirmationSerializer,SearchSerializer
from .service import create_location,update_location,change_pin,confirm_location,LocationConflict


def mutation(operation):
    try:return Response(LocationSerializer(operation()).data)
    except Location.DoesNotExist:return Response({'detail':'Location not found'},status=404)
    except LocationConflict as exc:return Response({'detail':str(exc)},status=409)
    except ValidationError as exc:
        return Response(getattr(exc,'message_dict',{'detail':exc.messages}),status=400)
    except ValueError as exc:return Response({'detail':str(exc)},status=400)


@api_view(['GET','POST'])
def locations(request):
    if request.method=='POST':
        serializer=CreateSerializer(data=request.data);serializer.is_valid(raise_exception=True)
        result=mutation(lambda:create_location(**serializer.validated_data,actor=request.user))
        if result.status_code==200:result.status_code=201
        return result
    if 'q' in request.query_params:
        return Response({'detail':'Submit search text in the private search request body.'},status=400)
    return listed_locations(request,request.query_params)


def listed_locations(request,filters):
    queryset=Location.objects.select_related('current_revision')
    status=filters.get('status')
    if status is None:queryset=queryset.exclude(status='archived')
    elif status!='all':
        if status not in Location.Status.values:return Response({'detail':'Invalid location status filter'},status=400)
        queryset=queryset.filter(status=status)
    if state:=filters.get('state'):queryset=queryset.filter(state__iexact=state)
    if asset:=filters.get('asset_type'):
        if asset not in Location.AssetType.values:return Response({'detail':'Invalid asset type filter'},status=400)
        queryset=queryset.filter(asset_type=asset)
    if query:=filters.get('q'):
        if len(query)>200:return Response({'detail':'Search text is too long'},status=400)
        queryset=queryset.filter(Q(name__icontains=query)|Q(address__icontains=query))
    paginator=PageNumberPagination()
    page=paginator.paginate_queryset(queryset,request)
    return paginator.get_paginated_response(LocationSerializer(page,many=True).data)


@api_view(['POST'])
def search(request):
    serializer=SearchSerializer(data=request.data);serializer.is_valid(raise_exception=True)
    return listed_locations(request,serializer.validated_data)

@api_view(['GET','PATCH'])
def location_detail(request,location_id):
    if request.method=='GET':
        item=get_object_or_404(Location.objects.select_related('current_revision'),pk=location_id)
        return Response(LocationSerializer(item).data)
    serializer=UpdateSerializer(data=request.data);serializer.is_valid(raise_exception=True)
    values=dict(serializer.validated_data);version=values.pop('expected_version')
    return mutation(lambda:update_location(location_id=location_id,expected_version=version,attributes=values,actor=request.user))


@api_view(['POST'])
def pin(request,location_id):
    serializer=PinSerializer(data=request.data);serializer.is_valid(raise_exception=True)
    return mutation(lambda:change_pin(location_id=location_id,actor=request.user,
        context={'nature':'User-provided'},**serializer.validated_data))


@api_view(['POST'])
def confirm(request,location_id):
    serializer=ConfirmationSerializer(data=request.data);serializer.is_valid(raise_exception=True)
    return mutation(lambda:confirm_location(location_id=location_id,actor=request.user,**serializer.validated_data))


@api_view(['GET'])
def history(request,location_id):
    item=get_object_or_404(Location,pk=location_id)
    queryset=item.audit_events.select_related('actor').order_by('-created_at','-id')
    paginator=PageNumberPagination();page=paginator.paginate_queryset(queryset,request)
    return paginator.get_paginated_response([{'id':entry.id,'action':entry.action,
        'actor':entry.actor.email if entry.actor else None,'created_at':entry.created_at,
        'before':entry.before,'after':entry.after} for entry in page])
