from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from habit_tracker.models.habit import Habit
from habit_tracker.models.habit_schedule import HabitSchedule
from habit_tracker.services.schedule import local_today
from habit_tracker.models.user import User
from habit_tracker.schemas.habit import HabitCreate, HabitUpdate


class HabitNotFound(Exception):
    pass


async def create_habit(session: AsyncSession, user: User, data: HabitCreate) -> Habit:
    habit = Habit(
        user_id=user.id,
        name=data.name,
        description=data.description,
        unit=data.unit,
        target_value=data.target_value,
    )
    session.add(habit)
    await session.flush()  # assigns habit.id without ending the transaction

    schedule = HabitSchedule(
        habit_id=habit.id,
        frequency_type=data.frequency_type,
        frequency_config=data.frequency_config,
        effective_from=local_today(user),
    )
    session.add(schedule)

    await session.commit()
    await session.refresh(habit)
    return habit


async def list_habits(session: AsyncSession, user: User, include_archived: bool) -> list[Habit]:
    stmt = select(Habit).where(Habit.user_id == user.id)
    if not include_archived:
        stmt = stmt.where(Habit.archived_at.is_(None))
    result = await session.execute(stmt.order_by(Habit.id))
    return list(result.scalars().all())


async def get_owned_habit(session: AsyncSession, user: User, habit_id: int) -> Habit:
    result = await session.execute(select(Habit).where(Habit.id == habit_id, Habit.user_id == user.id))
    habit = result.scalar_one_or_none()
    if habit is None:
        raise HabitNotFound(habit_id)
    return habit


async def update_habit(session: AsyncSession, user: User, habit_id: int, data: HabitUpdate) -> Habit:
    habit = await get_owned_habit(session, user, habit_id)

    for field in ("name", "description", "unit", "target_value"):
        value = getattr(data, field)
        if value is not None:
            setattr(habit, field, value)

    if data.frequency_type is not None:
        # A frequency change appends a new HabitSchedule row rather than
        # mutating one in place, so past entries stay judged by the
        # schedule that was active when they were logged — see
        # ARCHITECTURE.md.
        session.add(
            HabitSchedule(
                habit_id=habit.id,
                frequency_type=data.frequency_type,
                frequency_config=data.frequency_config,
                effective_from=local_today(user),
            )
        )

    await session.commit()
    await session.refresh(habit)
    return habit


async def archive_habit(session: AsyncSession, user: User, habit_id: int) -> Habit:
    habit = await get_owned_habit(session, user, habit_id)
    habit.archived_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(habit)
    return habit


async def restore_habit(session: AsyncSession, user: User, habit_id: int) -> Habit:
    habit = await get_owned_habit(session, user, habit_id)
    habit.archived_at = None
    await session.commit()
    await session.refresh(habit)
    return habit
