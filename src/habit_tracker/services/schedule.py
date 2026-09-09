from datetime import date, datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from habit_tracker.models.habit_schedule import FrequencyType, HabitSchedule
from habit_tracker.models.user import User


def local_today(user: User, now: Optional[datetime] = None) -> date:
    """The user's current calendar date, respecting their configured
    timezone and day-start-hour boundary (ARCHITECTURE.md / REQUIREMENTS.md
    "Day boundary" — e.g. day_start_hour=3 means a 2am moment still counts
    as the previous day).

    `now` is injectable (must be tz-aware) so callers/tests can pin the
    moment being evaluated; production callers omit it and get the real
    current time.
    """
    now = now or datetime.now(timezone.utc)
    now_local = now.astimezone(ZoneInfo(user.timezone))
    shifted = now_local - timedelta(hours=user.day_start_hour)
    return shifted.date()


def is_due_on(schedule: HabitSchedule, on_date: date) -> bool:
    """Whether a habit following `schedule` has a scheduled obligation on
    `on_date`. `times_per_week` habits have no fixed due days — any day
    can contribute toward the week's target — so every day is "due"."""
    if schedule.frequency_type == FrequencyType.DAILY:
        return True
    if schedule.frequency_type == FrequencyType.WEEKLY_DAYS:
        configured_days = schedule.frequency_config.get("days", [])
        return on_date.weekday() in configured_days
    if schedule.frequency_type == FrequencyType.TIMES_PER_WEEK:
        return True
    raise ValueError(f"unknown frequency_type: {schedule.frequency_type}")


def period_key(schedule: HabitSchedule, on_date: date) -> date:
    """The streak "period" `on_date` belongs to (ARCHITECTURE.md's Streak
    design): for daily/weekly_days habits a period is the day itself; for
    times_per_week habits a period is the week, represented by that week's
    Monday, so two dates in the same ISO week collapse to one key and a
    week boundary produces a different one."""
    if schedule.frequency_type == FrequencyType.TIMES_PER_WEEK:
        return on_date - timedelta(days=on_date.weekday())
    return on_date


async def active_schedule_as_of(
    session: AsyncSession, habit_id: int, as_of: date
) -> Optional[HabitSchedule]:
    """The schedule in force for `as_of`, per ARCHITECTURE.md: the latest
    row with effective_from <= as_of. Ties (two rows sharing the same
    effective_from, e.g. two edits made the same day) break toward the
    higher id — the more recently created row — rather than depending on
    undefined ordering.
    """
    result = await session.execute(
        select(HabitSchedule)
        .where(HabitSchedule.habit_id == habit_id, HabitSchedule.effective_from <= as_of)
        .order_by(HabitSchedule.effective_from.desc(), HabitSchedule.id.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()
