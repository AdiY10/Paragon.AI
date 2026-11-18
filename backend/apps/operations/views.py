from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.decorators import api_view,permission_classes
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from apps.accounts.permissions import IsAdministrator
from .models import JobRun
from .registry import REGISTRY
from .service import enqueue_job

FIELDS=['id','kind','scope','queue','status','attempts','max_attempts','created_at',
    'started_at','finished_at','heartbeat_at','next_attempt_at','recovery_count','last_recovered_at','records','error_code','rerun_of_id']


def payload(job):
    return {key:getattr(job,key) for key in FIELDS}


class SubmitSerializer(serializers.Serializer):
    kind=serializers.ChoiceField(choices=sorted(REGISTRY))
    scope=serializers.ChoiceField(choices=['global'],default='global')


class IdempotencySerializer(serializers.Serializer):
    key=serializers.UUIDField()


def request_key(request):
    value=IdempotencySerializer(data={'key':request.headers.get('Idempotency-Key')})
    value.is_valid(raise_exception=True)
    return str(value.validated_data['key'])


@api_view(['GET','POST'])
@permission_classes([IsAdministrator])
def jobs(request):
    if request.method=='GET':
        paginator=PageNumberPagination()
        page=paginator.paginate_queryset(JobRun.objects.all(),request)
        return paginator.get_paginated_response([payload(job) for job in page])
    serializer=SubmitSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    key=request_key(request)
    job,created=enqueue_job(**serializer.validated_data,dedup_key=f'manual:{request.user.pk}:{key}',requested_by=request.user)
    return Response(payload(job),status=202 if created else 200)


@api_view(['POST'])
@permission_classes([IsAdministrator])
def rerun(request,job_id):
    key=request_key(request)
    original=get_object_or_404(JobRun,pk=job_id)
    if original.status not in (JobRun.Status.SUCCEEDED,JobRun.Status.FAILED):
        return Response({'detail':'This run is still active; wait for completion or recovery.'},status=409)
    try:
        job,created=enqueue_job(kind=original.kind,scope=original.scope,parameters=original.parameters,
            dedup_key=f'rerun:{original.id}:{request.user.pk}:{key}',requested_by=request.user,rerun_of=original)
    except ValueError:
        return Response({'detail':'This job is no longer compatible with a registered handler.'},status=400)
    return Response(payload(job),status=202 if created else 200)


@api_view(['GET'])
@permission_classes([IsAdministrator])
def schedules(request):
    from .models import JobSchedule,SchedulerState
    items=[]
    for schedule in JobSchedule.objects.all():
        items.append({'name':schedule.name,'kind':schedule.kind,'enabled':schedule.enabled,
            'calendar':schedule.calendar,'next_due_at':schedule.next_due_at,
            'last_dispatched_at':schedule.last_dispatched_at,
            'blocked_reason':None if schedule.kind in REGISTRY else 'HANDLER_NOT_IMPLEMENTED'})
    state=SchedulerState.objects.filter(name='primary').first()
    return Response({'schedules':items,'last_tick_at':state.last_tick_at if state else None})
