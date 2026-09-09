from datetime import date, datetime, timedelta, timezone

from habit_tracker.models.entry import Entry, EntryStatus
from habit_tracker.models.habit import Habit
from habit_tracker.models.habit_schedule import FrequencyType, HabitSchedule
from habit_tracker.models.user import User
from habit_tracker.services.streak import reconcile

TODAY = date.today()


async def _make_user(db_session, email):
    user = User(email=email, hashed_password="x", timezone="UTC", day_start_hour=0)
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


async def _make_habit(db_session, user, effective_from):
    habit = Habit(user_id=user.id, name="Frozen habit")
    db_session.add(habit)
    await db_session.flush()
    db_session.add(
        HabitSchedule(habit_id=habit.id, frequency_type=FrequencyType.DAILY, frequency_config={}, effective_from=effective_from)
    )
    await db_session.commit()
    await db_session.refresh(habit)
    return habit


async def test_archived_habit_is_untouched_by_reconcile(db_session):
    """PLAN.md Phase 5 item 7 acceptance: after archiving, further elapsed
    time plus a reconciliation pass does not change current_streak."""
    user = await _make_user(db_session, "frozen@example.com")
    habit = await _make_habit(db_session, user, TODAY - timedelta(days=20))

    # A streak that ran up to a week ago, then nothing — if this habit
    # were active, reconcile() would find the elapsed unsatisfied days
    # and reset current_streak to 0.
    for i in range(5):
        db_session.add(
            Entry(
                habit_id=habit.id,
                local_date=TODAY - timedelta(days=10) + timedelta(days=i),
                completed_at=datetime.now(timezone.utc),
                status=EntryStatus.DONE,
            )
        )
    await db_session.commit()

    # Archive it with a manually-set streak value, simulating "frozen at
    # whatever it was when archived" rather than what recompute would say.
    habit.archived_at = datetime.now(timezone.utc)
    habit.current_streak = 5
    habit.longest_streak = 5
    await db_session.commit()

    await reconcile(db_session, habit)

    assert habit.current_streak == 5
    assert habit.longest_streak == 5


async def test_non_archived_habit_is_recomputed_by_reconcile(db_session):
    user = await _make_user(db_session, "not-frozen@example.com")
    habit = await _make_habit(db_session, user, TODAY - timedelta(days=20))

    for i in range(5):
        db_session.add(
            Entry(
                habit_id=habit.id,
                local_date=TODAY - timedelta(days=10) + timedelta(days=i),
                completed_at=datetime.now(timezone.utc),
                status=EntryStatus.DONE,
            )
        )
    await db_session.commit()

    habit.current_streak = 999  # stale/wrong on purpose
    await db_session.commit()

    await reconcile(db_session, habit)

    # The elapsed days since the 5-day run ended (day-6..today, all
    # unsatisfied) are a real break — current_streak must reflect that,
    # not the stale value.
    assert habit.current_streak == 0
    assert habit.longest_streak == 5
