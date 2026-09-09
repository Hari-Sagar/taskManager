from datetime import date, datetime, timezone

import pytest
from sqlalchemy.exc import IntegrityError

from habit_tracker.models.entry import Entry, EntryStatus
from habit_tracker.models.habit import Habit
from habit_tracker.models.user import User


async def test_duplicate_habit_local_date_rejected(db_session):
    """PLAN.md item 7 acceptance: the unique constraint on
    (habit_id, local_date) rejects a duplicate insert."""
    user = User(email="entry-owner@example.com", hashed_password="x")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    habit = Habit(user_id=user.id, name="Read")
    db_session.add(habit)
    await db_session.commit()
    await db_session.refresh(habit)

    today = date(2026, 9, 8)
    now = datetime.now(timezone.utc)

    db_session.add(Entry(habit_id=habit.id, local_date=today, completed_at=now, status=EntryStatus.DONE))
    await db_session.commit()

    db_session.add(Entry(habit_id=habit.id, local_date=today, completed_at=now, status=EntryStatus.DONE))
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()
