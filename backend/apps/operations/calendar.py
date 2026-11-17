"""Wall-clock recurrence with explicit gap/fold rules for US Eastern schedules."""
from dataclasses import dataclass
from datetime import datetime,timedelta,time,timezone
from zoneinfo import ZoneInfo

@dataclass(frozen=True)
class CalendarRule:
    cadence: str
    hour: int
    minute: int=0
    weekday: int|None=None
    day: int|None=None
    zone: str='America/New_York'

    def __post_init__(self):
        if self.cadence not in ('daily','weekly','monthly'):
            raise ValueError('Unsupported calendar cadence')
        if type(self.hour) is not int or not 0<=self.hour<=23 or type(self.minute) is not int or not 0<=self.minute<=59:
            raise ValueError('Invalid calendar time')
        if self.cadence=='weekly':
            if type(self.weekday) is not int or not 0<=self.weekday<=6 or self.day is not None:
                raise ValueError('Weekly schedules require one weekday')
        elif self.cadence=='monthly':
            if type(self.day) is not int or not 1<=self.day<=31 or self.weekday is not None:
                raise ValueError('Monthly schedules require one day')
        elif self.day is not None or self.weekday is not None:
            raise ValueError('Daily schedules cannot restrict the date')
        if self.zone!='America/New_York':
            raise ValueError('Release 1 schedules use America/New_York')


def resolve_wall_time(wall: datetime,zone: ZoneInfo) -> datetime:
    if wall.tzinfo is not None:
        raise ValueError('Wall time must be naive before timezone resolution')
    for _ in range(181):
        candidates=set()
        for fold in (0,1):
            candidate=wall.replace(tzinfo=zone,fold=fold).astimezone(timezone.utc)
            if candidate.astimezone(zone).replace(tzinfo=None)==wall:
                candidates.add(candidate)
        if candidates:
            return min(candidates)  # A repeated fall-back time occurs once, at its first occurrence.
        wall+=timedelta(minutes=1)  # A nonexistent time runs at the next valid wall-clock minute.
    raise ValueError('Could not resolve local calendar time')


def next_occurrence(rule: CalendarRule,after: datetime) -> datetime:
    if after.tzinfo is None or after.utcoffset() is None:
        raise ValueError('Calendar anchor must be timezone-aware')
    zone=ZoneInfo(rule.zone)
    local_date=after.astimezone(zone).date()
    for offset in range(370):
        date=local_date+timedelta(days=offset)
        if rule.cadence=='weekly' and date.weekday()!=rule.weekday:
            continue
        if rule.cadence=='monthly' and date.day!=rule.day:
            continue
        occurrence=resolve_wall_time(datetime.combine(date,time(rule.hour,rule.minute)),zone)
        if occurrence>after:
            return occurrence
    raise ValueError('No recurrence found within supported calendar horizon')


def coalesce_due(rule: CalendarRule,next_due: datetime,now: datetime):
    if next_due.tzinfo is None or now.tzinfo is None:
        raise ValueError('Due-time anchors must be timezone-aware')
    if next_due>now:
        return None,0,next_due
    latest=next_due
    missed=0
    for _ in range(10000):
        following=next_occurrence(rule,latest)
        if following>now:
            return latest,missed,following
        latest=following
        missed+=1
    raise ValueError('Schedule backlog exceeds the recovery horizon')
