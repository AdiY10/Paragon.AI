from dataclasses import asdict
from datetime import timedelta
from pathlib import Path
import re
from zoneinfo import ZoneInfo
import yaml
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from .calendar import CalendarRule,next_occurrence,coalesce_due
from .models import JobSchedule,ScheduleOccurrence,SchedulerState
from .registry import REGISTRY
from .service import enqueue_job
from .recovery import recover_jobs


def load_definitions(path=None):
    document=yaml.safe_load(Path(path or settings.BASE_DIR/'config/schedules.yaml').read_text())
    if not isinstance(document,dict) or document.get('schema_version')!=1 or not isinstance(document.get('schedules'),list):
        raise ValueError('Invalid schedule definition schema')
    parsed=[];seen=set()
    for item in document['schedules']:
        if not isinstance(item,dict) or not {'name','kind','cadence','hour'}<=set(item) or set(item)-{'name','kind','cadence','hour','minute','weekday','day','enabled'}:
            raise ValueError('Invalid schedule definition fields')
        if any(not isinstance(item[key],str) or not re.fullmatch(r'[a-z][a-z0-9_]{0,63}',item[key]) for key in ('name','kind')) or item['name'] in seen:
            raise ValueError('Invalid or duplicate schedule name')
        seen.add(item['name'])
        if 'enabled' in item and item['enabled'] is not False:
            raise ValueError('enabled may only be false (a switched-off schedule)')
        rule=CalendarRule(**{key:value for key,value in item.items() if key not in ('name','kind','enabled')})
        parsed.append((item['name'],item['kind'],rule,item.get('enabled',True)))
    return parsed


@transaction.atomic
def sync_schedules(*,path=None,enable_available=False,now=None):
    now=now or timezone.now()
    definitions=load_definitions(path)
    for name,kind,rule,allowed in definitions:
        calendar=asdict(rule)
        schedule,created=JobSchedule.objects.get_or_create(name=name,
            defaults={'kind':kind,'calendar':calendar,'next_due_at':next_occurrence(rule,now)})
        if not created and (schedule.calendar!=calendar or schedule.kind!=kind):
            schedule.calendar=calendar;schedule.kind=kind
            schedule.next_due_at=next_occurrence(rule,now)
        if kind not in REGISTRY or not allowed:
            schedule.enabled=False
        elif enable_available:
            schedule.enabled=True
        schedule.save()
    return len(definitions)


@transaction.atomic
def acquire_leader(owner,now):
    SchedulerState.objects.get_or_create(name='primary',defaults={'lease_until':now})
    state=SchedulerState.objects.select_for_update().get(name='primary')
    if state.owner not in (None,owner) and state.lease_until>now:
        return False
    state.owner=owner;state.lease_until=now+timedelta(seconds=60);state.last_tick_at=now
    state.save()
    return True


def release_leader(owner):
    SchedulerState.objects.filter(name='primary',owner=owner).update(owner=None,lease_until=timezone.now())


def dispatch_due(*,owner,now=None):
    now=now or timezone.now()
    if timezone.is_naive(now):raise ValueError('Scheduler time must be timezone-aware')
    if not acquire_leader(owner,now):return {'leader':False,'dispatched':0,'blocked':0}
    recovery=recover_jobs(now=now)
    dispatched=blocked=0
    names=list(JobSchedule.objects.filter(enabled=True,next_due_at__lte=now).values_list('name',flat=True))
    for name in names:
        with transaction.atomic():
            schedule=JobSchedule.objects.select_for_update().get(pk=name)
            if not schedule.enabled or schedule.next_due_at>now:continue
            if schedule.kind not in REGISTRY:
                blocked+=1;continue
            rule=CalendarRule(**schedule.calendar)
            due,missed,following=coalesce_due(rule,schedule.next_due_at,now)
            local_date=due.astimezone(ZoneInfo(rule.zone)).date()
            if not ScheduleOccurrence.objects.filter(schedule=schedule,local_date=local_date).exists():
                job,_=enqueue_job(kind=schedule.kind,scope=schedule.scope,
                    dedup_key=f'scheduled:{schedule.name}:{local_date.isoformat()}')
                ScheduleOccurrence.objects.create(schedule=schedule,local_date=local_date,
                    scheduled_for=due,dispatched_at=now,missed_count=missed,
                    delay_seconds=max(0,int((now-due).total_seconds())),
                    calendar_at_dispatch=schedule.calendar,job=job)
                dispatched+=1
            schedule.next_due_at=following;schedule.last_dispatched_at=now
            schedule.save(update_fields=['next_due_at','last_dispatched_at','updated_at'])
    return {'leader':True,'dispatched':dispatched,'blocked':blocked,'recovery':recovery,'analysis':_maybe_sweep(now)}


_last_sweep=None

def _maybe_sweep(now):
    """Automatic analysis sweep (B3a), at most every 5 minutes on the scheduler leader."""
    global _last_sweep
    from django.conf import settings
    from apps.area import analysis
    if not getattr(settings,'AUTO_ANALYZE',False):return None
    if _last_sweep is not None and now-_last_sweep<analysis.SWEEP_EVERY:return None
    _last_sweep=now
    try:
        return analysis.sweep(now=now)
    except Exception:
        import logging
        logging.getLogger(__name__).exception('analysis sweep failed')
        return {'error':True}
