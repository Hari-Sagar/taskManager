from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from habit_tracker.models.entry import Entry
from habit_tracker.models.habit import Habit
from habit_tracker.models.user import User
from habit_tracker.schemas.today import TodayItem
from habit_tracker.services.schedule import active_schedule_as_of, is_due_on, local_today


async def get_today(session: AsyncSession, user: User) -> List[TodayItem]:
    """Reads Habit.current_streak directly — no recompute()/apply_checkin()
    call. This is the app's most-hit endpoint (ARCHITECTURE.md's "Why
    read-time computation was rejected" #1); the running counter exists
    precisely so this stays O(1) per habit."""
    today = local_today(user)

    result = await session.execute(
        select(Habit).where(Habit.user_id == user.id, Habit.archived_at.is_(None)).order_by(Habit.id)
    )
    habits = result.scalars().all()

    items = []
    for habit in habits:
        schedule = await active_schedule_as_of(session, habit.id, today)
        if schedule is None or not is_due_on(schedule, today):
            continue

        entry_result = await session.execute(
            select(Entry).where(Entry.habit_id == habit.id, Entry.local_date == today)
        )
        entry = entry_result.scalar_one_or_none()
        status = entry.status.value if entry is not None else "pending"

        items.append(
            TodayItem(habit_id=habit.id, name=habit.name, status=status, current_streak=habit.current_streak)
        )
    return items
