from datetime import datetime,timezone
import pytest
from apps.operations.calendar import CalendarRule,next_occurrence,coalesce_due


def utc(value):return datetime.fromisoformat(value).replace(tzinfo=timezone.utc)


def test_monday_brief_remains_seven_am_across_spring_dst():
    rule=CalendarRule('weekly',7,weekday=0)
    before=next_occurrence(rule,utc('2026-02-28T00:00:00'))
    after=next_occurrence(rule,utc('2026-03-07T00:00:00'))
    assert before==utc('2026-03-02T12:00:00')
    assert after==utc('2026-03-09T11:00:00')


def test_spring_gap_runs_at_first_valid_minute_not_shifted_by_full_hour():
    rule=CalendarRule('daily',2,30)
    assert next_occurrence(rule,utc('2026-03-08T00:00:00'))==utc('2026-03-08T07:00:00')


def test_fall_fold_runs_once_at_first_occurrence():
    rule=CalendarRule('daily',1,30)
    first=next_occurrence(rule,utc('2026-11-01T00:00:00'))
    assert first==utc('2026-11-01T05:30:00')
    assert next_occurrence(rule,first)==utc('2026-11-02T06:30:00')
    assert next_occurrence(rule,utc('2026-11-01T05:45:00'))==utc('2026-11-02T06:30:00')


def test_monthly_day_31_skips_month_without_that_day():
    assert next_occurrence(CalendarRule('monthly',4,day=31),utc('2026-02-01T00:00:00'))==utc('2026-03-31T08:00:00')


def test_coalesce_retains_latest_due_and_count_of_skipped_occurrences():
    rule=CalendarRule('daily',6)
    latest,missed,following=coalesce_due(rule,utc('2026-11-14T11:00:00'),utc('2026-11-17T12:00:00'))
    assert latest==utc('2026-11-17T11:00:00') and missed==3
    assert following==utc('2026-11-18T11:00:00')


def test_exact_due_time_is_included_once():
    due=utc('2026-11-17T11:00:00');rule=CalendarRule('daily',6)
    assert coalesce_due(rule,due,due)[0]==due
    assert coalesce_due(rule,due,due)[1]==0


@pytest.mark.parametrize('kwargs',[{'cadence':'hourly','hour':4},{'cadence':'weekly','hour':4},{'cadence':'daily','hour':24},{'cadence':'monthly','hour':4,'day':0}])
def test_invalid_calendar_rules_fail(kwargs):
    with pytest.raises(ValueError):CalendarRule(**kwargs)


def test_naive_calendar_anchor_is_rejected():
    with pytest.raises(ValueError,match='timezone-aware'):
        next_occurrence(CalendarRule('daily',6),datetime(2026,1,1))
