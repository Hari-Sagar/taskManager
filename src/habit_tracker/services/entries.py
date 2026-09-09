from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from habit_tracker.models.entry import Entry
from habit_tracker.models.habit import Habit
from habit_tracker.models.user import User
from habit_tracker.schemas.entry import EntryCreate, EntryUpdate
from habit_tracker.services import habits as habits_service
from habit_tracker.services import streak as streak_service
from habit_tracker.services.schedule import local_today


class EntryNotFound(Exception):
    pass


class DuplicateEntry(Exception):
    pass


async def _get_entry(session: AsyncSession, habit_id: int, local_date: date) -> Entry:
    result = await session.execute(
        select(Entry).where(Entry.habit_id == habit_id, Entry.local_date == local_date)
    )
    entry = result.scalar_one_or_none()
    if entry is None:
        raise EntryNotFound(local_date)
    return entry


async def create_entry(session: AsyncSession, user: User, habit_id: int, data: EntryCreate) -> Entry:
    habit: Habit = await habits_service.get_owned_habit(session, user, habit_id)
    local_date = data.local_date or local_today(user)

    existing = await session.execute(
        select(Entry).where(Entry.habit_id == habit.id, Entry.local_date == local_date)
    )
    if existing.scalar_one_or_none() is not None:
        raise DuplicateEntry(local_date)

    entry = Entry(
        habit_id=habit.id,
        local_date=local_date,
        completed_at=datetime.now(timezone.utc),
        status=data.status,
        value=data.value,
    )
    session.add(entry)
    await session.flush()  # assigns entry.id, visible to apply_checkin's queries, within the still-open transaction

    # Entry insert + streak counter update share this one transaction —
    # see ARCHITECTURE.md's "Transaction boundary": if apply_checkin
    # raises, the commit below never happens and get_db's exception
    # handler rolls both back together.
    await streak_service.apply_checkin(session, habit, entry)

    await session.commit()
    await session.refresh(entry)
    return entry


async def update_entry(
    session: AsyncSession, user: User, habit_id: int, local_date: date, data: EntryUpdate
) -> Entry:
    habit = await habits_service.get_owned_habit(session, user, habit_id)
    entry = await _get_entry(session, habit_id, local_date)

    if data.status is not None:
        entry.status = data.status
    if data.value is not None:
        entry.value = data.value
    entry.edited_at = datetime.now(timezone.utc)
    await session.flush()

    # Edits to past entries never take the apply_checkin fast path — see
    # ARCHITECTURE.md: correctness wins over the O(1) shortcut here.
    await streak_service.recompute(session, habit)

    await session.commit()
    await session.refresh(entry)
    return entry


async def delete_entry(session: AsyncSession, user: User, habit_id: int, local_date: date) -> None:
    habit = await habits_service.get_owned_habit(session, user, habit_id)
    entry = await _get_entry(session, habit_id, local_date)
    await session.delete(entry)
    await session.flush()

    await streak_service.recompute(session, habit)

    await session.commit()
