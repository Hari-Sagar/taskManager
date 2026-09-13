from datetime import datetime, timedelta, timezone

from habit_tracker.models.entry import Entry, EntryStatus
from habit_tracker.models.habit import Habit
from habit_tracker.models.habit_schedule import FrequencyType, HabitSchedule
from habit_tracker.models.user import User
from habit_tracker.jobs.scheduler import run_nightly_reconciliation

# UTC, not local date.today() — matches local_today() for these
# UTC-timezone test users regardless of the local machine's timezone or
# time of day (they disagree for hours near midnight UTC otherwise).
TODAY = datetime.now(timezone.utc).date()


async def _make_user(db_session, email):
    user = User(email=email, hashed_password="x", timezone="UTC", day_start_hour=0)
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


async def _make_habit(db_session, user, effective_from, archived=False):
    habit = Habit(user_id=user.id, name="Habit")
    if archived:
        habit.archived_at = datetime.now(timezone.utc)
    db_session.add(habit)
    await db_session.flush()
    db_session.add(
        HabitSchedule(habit_id=habit.id, frequency_type=FrequencyType.DAILY, frequency_config={}, effective_from=effective_from)
    )
    await db_session.commit()
    await db_session.refresh(habit)
    return habit


def _add_entry(db_session, habit, local_date):
    db_session.add(
        Entry(habit_id=habit.id, local_date=local_date, completed_at=datetime.now(timezone.utc), status=EntryStatus.DONE)
    )


async def test_reconciliation_drops_streak_for_habit_with_a_passive_break(db_session):
    user = await _make_user(db_session, "nightly-break@example.com")
    habit = await _make_habit(db_session, user, TODAY - timedelta(days=20))
    for i in range(5):
        _add_entry(db_session, habit, TODAY - timedelta(days=10) + timedelta(days=i))
    await db_session.commit()

    habit.current_streak = 999  # stale
    await db_session.commit()

    await run_nightly_reconciliation(db_session)

    assert habit.current_streak == 0
    assert habit.longest_streak == 5


async def test_reconciliation_skips_archived_habits(db_session):
    user = await _make_user(db_session, "nightly-archived@example.com")
    habit = await _make_habit(db_session, user, TODAY - timedelta(days=20), archived=True)
    habit.current_streak = 42
    await db_session.commit()

    await run_nightly_reconciliation(db_session)

    assert habit.current_streak == 42


async def test_reconciliation_updates_multiple_habits_independently(db_session):
    user = await _make_user(db_session, "nightly-multi@example.com")
    ok_habit = await _make_habit(db_session, user, TODAY - timedelta(days=5))
    _add_entry(db_session, ok_habit, TODAY)
    broken_habit = await _make_habit(db_session, user, TODAY - timedelta(days=20))
    for i in range(3):
        _add_entry(db_session, broken_habit, TODAY - timedelta(days=15) + timedelta(days=i))
    await db_session.commit()

    await run_nightly_reconciliation(db_session)

    assert ok_habit.current_streak == 1
    assert broken_habit.current_streak == 0
    assert broken_habit.longest_streak == 3
