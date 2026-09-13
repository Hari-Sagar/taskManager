from datetime import datetime, timedelta, timezone

from habit_tracker.models.entry import Entry, EntryStatus
from habit_tracker.models.habit import Habit
from habit_tracker.models.habit_schedule import FrequencyType, HabitSchedule
from habit_tracker.models.user import User
from habit_tracker.services.streak import recompute

# user.timezone="UTC", day_start_hour=0 in these tests, so this must be
# actual UTC — not date.today()'s local system timezone, which disagrees
# with UTC for several hours a day whenever the local machine isn't
# itself on UTC (this bit us for real: these tests flaked exactly when
# that mismatch window was hit).
TODAY = datetime.now(timezone.utc).date()


async def _make_user(db_session, email):
    user = User(email=email, hashed_password="x", timezone="UTC", day_start_hour=0)
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


async def _make_habit(db_session, user, frequency_type, frequency_config, effective_from, target_value=None):
    habit = Habit(user_id=user.id, name="Test habit", target_value=target_value)
    db_session.add(habit)
    await db_session.flush()
    db_session.add(
        HabitSchedule(
            habit_id=habit.id,
            frequency_type=frequency_type,
            frequency_config=frequency_config,
            effective_from=effective_from,
        )
    )
    await db_session.commit()
    await db_session.refresh(habit)
    return habit


def _add_entry(db_session, habit, local_date, status=EntryStatus.DONE, value=None):
    db_session.add(
        Entry(
            habit_id=habit.id,
            local_date=local_date,
            completed_at=datetime.now(timezone.utc),
            status=status,
            value=value,
        )
    )


async def test_no_entries_leaves_streak_at_zero(db_session):
    user = await _make_user(db_session, "recompute-empty@example.com")
    habit = await _make_habit(db_session, user, FrequencyType.DAILY, {}, TODAY - timedelta(days=10))

    await recompute(db_session, habit)

    assert habit.current_streak == 0
    assert habit.longest_streak == 0
    assert habit.streak_last_counted_period_start is None


async def test_consecutive_daily_entries_ending_today(db_session):
    user = await _make_user(db_session, "recompute-consecutive@example.com")
    habit = await _make_habit(db_session, user, FrequencyType.DAILY, {}, TODAY - timedelta(days=10))
    for i in range(5):
        _add_entry(db_session, habit, TODAY - timedelta(days=4 - i))
    await db_session.commit()

    await recompute(db_session, habit)

    assert habit.current_streak == 5
    assert habit.longest_streak == 5
    assert habit.streak_last_counted_period_start == TODAY


async def test_gap_breaks_current_streak_but_longest_reflects_history(db_session):
    user = await _make_user(db_session, "recompute-gap@example.com")
    habit = await _make_habit(db_session, user, FrequencyType.DAILY, {}, TODAY - timedelta(days=20))

    # An earlier 6-day run, then a gap, then a shorter trailing 2-day run.
    for i in range(6):
        _add_entry(db_session, habit, TODAY - timedelta(days=15) + timedelta(days=i))
    # gap: days -9..-3 have no entries
    _add_entry(db_session, habit, TODAY - timedelta(days=1))
    _add_entry(db_session, habit, TODAY)
    await db_session.commit()

    await recompute(db_session, habit)

    assert habit.current_streak == 2
    assert habit.longest_streak == 6
    assert habit.streak_last_counted_period_start == TODAY


async def test_today_not_yet_checked_in_does_not_break_streak(db_session):
    user = await _make_user(db_session, "recompute-inprogress@example.com")
    habit = await _make_habit(db_session, user, FrequencyType.DAILY, {}, TODAY - timedelta(days=10))
    for i in range(3):
        _add_entry(db_session, habit, TODAY - timedelta(days=3 - i))  # ends yesterday
    await db_session.commit()

    await recompute(db_session, habit)

    assert habit.current_streak == 3
    assert habit.streak_last_counted_period_start == TODAY - timedelta(days=1)


async def test_times_per_week_only_counts_satisfied_weeks(db_session):
    user = await _make_user(db_session, "recompute-tpw@example.com")
    # Anchor everything to a fixed Monday so week boundaries are unambiguous.
    monday = TODAY - timedelta(days=TODAY.weekday())
    habit = await _make_habit(
        db_session, user, FrequencyType.TIMES_PER_WEEK, {"target": 3}, monday - timedelta(weeks=3)
    )

    # Week -2: only 2 done entries (not satisfied)
    week_minus_2 = monday - timedelta(weeks=2)
    _add_entry(db_session, habit, week_minus_2)
    _add_entry(db_session, habit, week_minus_2 + timedelta(days=1))

    # Week -1: 3 done entries (satisfied)
    week_minus_1 = monday - timedelta(weeks=1)
    _add_entry(db_session, habit, week_minus_1)
    _add_entry(db_session, habit, week_minus_1 + timedelta(days=1))
    _add_entry(db_session, habit, week_minus_1 + timedelta(days=2))

    # This week so far: 3 done entries already (satisfied, in-progress week)
    _add_entry(db_session, habit, monday)
    _add_entry(db_session, habit, monday + timedelta(days=1))
    if TODAY >= monday + timedelta(days=2):
        _add_entry(db_session, habit, monday + timedelta(days=2))
    await db_session.commit()

    await recompute(db_session, habit)

    # week -2 unsatisfied breaks the streak there; only week -1 (and maybe
    # this week, if it already hit target) form the trailing run.
    expected_current = 2 if TODAY >= monday + timedelta(days=2) else 1
    assert habit.current_streak == expected_current
    assert habit.longest_streak >= expected_current


async def test_quantifiable_habit_requires_target_to_qualify(db_session):
    user = await _make_user(db_session, "recompute-quant@example.com")
    habit = await _make_habit(
        db_session, user, FrequencyType.DAILY, {}, TODAY - timedelta(days=5), target_value=8
    )
    _add_entry(db_session, habit, TODAY - timedelta(days=1), value=8)  # meets target
    _add_entry(db_session, habit, TODAY, value=3)  # below target — doesn't qualify, but today gets grace anyway
    await db_session.commit()

    await recompute(db_session, habit)

    assert habit.current_streak == 1
    assert habit.streak_last_counted_period_start == TODAY - timedelta(days=1)
