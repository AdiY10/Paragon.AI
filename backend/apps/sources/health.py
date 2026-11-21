"""Scoped freshness and immutable check history; refresh failures retain last-good data."""
from datetime import timedelta
from django.db import transaction
from django.utils import timezone
from .models import SourceCheck, SourceDefinition, SourceHealth

ERROR_CODES={'TIMEOUT','HTTP_ERROR','SCHEMA_ERROR','NOT_CONFIGURED','STORAGE_ERROR','SOURCE_ERROR'}


def health_status(health, *, now=None):
    now=now or timezone.now()
    if health.consecutive_failures:
        return 'Failing'
    if health.last_success_at is None:
        return 'Not checked'
    days=health.source.stale_after_days
    if days is not None and now-health.last_success_at>timedelta(days=days):
        return 'Stale'
    if health.source_id=='SRC-13' and health.available_since and health.available_release!=health.processed_release and now-health.available_since>timedelta(days=14):
        return 'Stale'
    return 'OK'


@transaction.atomic
def record_check(*,source_id,scope,run_key,succeeded,completed_at=None,error_code='',snapshot=None,
        available_release=None,available_since=None):
    completed_at=completed_at or timezone.now()
    if timezone.is_naive(completed_at) or completed_at>timezone.now():
        raise ValueError('Check time must be timezone-aware and not in the future')
    if type(succeeded) is not bool or not scope or len(scope)>160 or not run_key or len(run_key)>160:
        raise ValueError('Invalid source check identity')
    if (succeeded and error_code) or (not succeeded and error_code not in ERROR_CODES):
        raise ValueError('Source failures require a sanitized error code; successes cannot contain errors')
    if snapshot is not None and (not succeeded or snapshot.source_id!=source_id or snapshot.scope!=scope or snapshot.retrieved_at>completed_at):
        raise ValueError('Snapshot does not belong to this successful source check')
    if available_release is not None and (not isinstance(available_release,str) or not available_release or len(available_release)>96):
        raise ValueError('Invalid available release')
    if available_since is not None and (timezone.is_naive(available_since) or available_since>completed_at):
        raise ValueError('Invalid release availability timestamp')
    source=SourceDefinition.objects.get(pk=source_id)
    SourceHealth.objects.get_or_create(source=source,scope=scope)
    health=SourceHealth.objects.select_for_update().get(source=source,scope=scope)
    check,created=SourceCheck.objects.get_or_create(source=source,scope=scope,run_key=run_key,
        defaults={'completed_at':completed_at,'succeeded':succeeded,'error_code':error_code,'snapshot':snapshot})
    if not created:
        if check.succeeded!=succeeded or check.error_code!=error_code or check.snapshot_id!=getattr(snapshot,'id',None):
            raise ValueError('Source check rerun conflicts with its immutable result')
        return health,False
    # Historical checks can supply a last-good cache, but cannot clear a newer
    # failure or claim a successful check today.
    is_latest=health.last_checked_at is None or completed_at>health.last_checked_at
    if succeeded:
        if health.last_success_at is None or completed_at>health.last_success_at:
            health.last_success_at=completed_at
        if snapshot is not None and (health.latest_snapshot_id is None or snapshot.retrieved_at>health.latest_snapshot.retrieved_at):
            health.latest_snapshot=snapshot
            health.processed_release=snapshot.release
        if is_latest and available_release is not None:
            if available_release!=health.available_release:
                health.available_release=available_release
                health.available_since=available_since or completed_at
            elif available_since is not None and (health.available_since is None or available_since<health.available_since):
                health.available_since=available_since
    if is_latest:
        health.last_checked_at=completed_at
        health.error_code='' if succeeded else error_code
    failures=SourceCheck.objects.filter(source=source,scope=scope,succeeded=False)
    if health.last_success_at is not None:
        failures=failures.filter(completed_at__gte=health.last_success_at)
    health.consecutive_failures=failures.count()
    health.error_code=failures.order_by("-completed_at","-id").first().error_code if health.consecutive_failures else ""
    health.save()
    _source_alert(health)
    return health,True


def _source_alert(health):
    """docs/06 §4.2: alert administrators after two consecutive failures of a source scope."""
    import hashlib
    from apps.operations.alerts import raise_alert,resolve_alert
    # Scopes can contain coordinates; key on a hash and never put the scope in the summary.
    key=f'source:{health.source_id}:{hashlib.sha256(health.scope.encode()).hexdigest()[:12]}'
    try:
        if health.consecutive_failures>=2:
            raise_alert(key,f'{health.source.name} failing ({health.consecutive_failures} checks in a row, {health.error_code})')
        elif health.consecutive_failures==0:
            resolve_alert(key)
    except Exception:
        import logging
        logging.getLogger(__name__).exception('source alert bookkeeping failed')


def health_payload(health, *, now=None):
    status=health_status(health,now=now)
    return {'scope':health.scope,'status':status,'last_checked_at':health.last_checked_at,
        'last_success_at':health.last_success_at,'consecutive_failures':health.consecutive_failures,
        'error_code':health.error_code or None,'snapshot_id':health.latest_snapshot_id,
        'data_period':health.latest_snapshot.data_period if health.latest_snapshot_id else None,
        'available_release':health.available_release or None,'processed_release':health.processed_release or None,
        'needs_alert':health.consecutive_failures>=2 or status=='Stale'}
