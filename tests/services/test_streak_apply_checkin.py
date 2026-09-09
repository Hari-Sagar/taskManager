from datetime import date, datetime, timedelta, timezone

from habit_tracker.models.entry import Entry, EntryStatus
from habit_tracker.models.habit import Habit
from habit_tracker.models.habit_schedule import FrequencyType, HabitSchedule
from habit_tracker.models.user import User
from habit_tracker.services import streak as streak_module

TODAY = date.today()


def _spy_on_recompute(monkeypatch):
    calls = []
    original = streak_module.recompute

    async def spy(session, habit):
        calls.append(habit.id)
        await original(session, habit)

    monkeypatch.setattr(streak_module, "recompute", spy)
    return calls


async def _make_user(db_session, email):
    user = User(email=email, hashed_password="x", timezone="UTC", day_start_hour=0)
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


async def _make_habit(db_session, user, frequency_type, frequency_config, effective_from):
    habit = Habit(user_id=user.id, name="Test habit")
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


async def _add_and_flush_entry(db_session, habit, local_date, value=None):
    entry = Entry(
        habit_id=habit.id,
        local_date=local_date,
        completed_at=datetime.now(timezone.utc),
        status=EntryStatus.DONE,
        value=value,
    )
    db_session.add(entry)
    await db_session.flush()
    return entry


async def test_fast_path_increments_without_calling_recompute(db_session, monkeypatch):
    user = await _make_user(db_session, "checkin-fast@example.com")
    habit = await _make_habit(db_session, user, FrequencyType.DAILY, {}, TODAY - timedelta(days=10))
    habit.current_streak = 2
    habit.longest_streak = 2
    habit.streak_last_counted_period_start = TODAY - timedelta(days=1)
    await db_session.commit()

    calls = _spy_on_recompute(monkeypatch)
    entry = await _add_and_flush_entry(db_session, habit, TODAY)

    await streak_module.apply_checkin(db_session, habit, entry)

    assert calls == []
    assert habit.current_streak == 3
    assert habit.longest_streak == 3
    assert habit.streak_last_counted_period_start == TODAY


async def test_first_ever_entry_falls_back_to_recompute(db_session, monkeypatch):
    user = await _make_user(db_session, "checkin-first@example.com")
    habit = await _make_habit(db_session, user, FrequencyType.DAILY, {}, TODAY - timedelta(days=10))
    assert habit.streak_last_counted_period_start is None

    calls = _spy_on_recompute(monkeypatch)
    entry = await _add_and_flush_entry(db_session, habit, TODAY)

    await streak_module.apply_checkin(db_session, habit, entry)

    assert calls == [habit.id]
    assert habit.current_streak == 1
    assert habit.streak_last_counted_period_start == TODAY

    # idempotency check: running the ground truth again changes nothing —
    # proves the fallback path already landed on the correct answer.
    before = (habit.current_streak, habit.longest_streak, habit.streak_last_counted_period_start)
    await streak_module.recompute(db_session, habit)
    after = (habit.current_streak, habit.longest_streak, habit.streak_last_counted_period_start)
    assert before == after


async def test_backfill_gap_falls_back_to_recompute(db_session, monkeypatch):
    user = await _make_user(db_session, "checkin-backfill@example.com")
    habit = await _make_habit(db_session, user, FrequencyType.DAILY, {}, TODAY - timedelta(days=10))
    habit.current_streak = 1
    habit.longest_streak = 1
    habit.streak_last_counted_period_start = TODAY - timedelta(days=5)
    await db_session.commit()

    calls = _spy_on_recompute(monkeypatch)
    # backfilling 3 days ago is not the expected next period (yesterday's
    # date), so this must fall back rather than blindly incrementing.
    entry = await _add_and_flush_entry(db_session, habit, TODAY - timedelta(days=3))

    await streak_module.apply_checkin(db_session, habit, entry)

    assert calls == [habit.id]
    before = (habit.current_streak, habit.longest_streak, habit.streak_last_counted_period_start)
    await streak_module.recompute(db_session, habit)
    after = (habit.current_streak, habit.longest_streak, habit.streak_last_counted_period_start)
    assert before == after


async def test_times_per_week_partial_week_is_a_noop(db_session, monkeypatch):
    user = await _make_user(db_session, "checkin-tpw-partial@example.com")
    monday = TODAY - timedelta(days=TODAY.weekday())
    habit = await _make_habit(
        db_session, user, FrequencyType.TIMES_PER_WEEK, {"target": 3}, monday - timedelta(weeks=1)
    )

    calls = _spy_on_recompute(monkeypatch)
    entry = await _add_and_flush_entry(db_session, habit, monday)  # 1st of 3 needed this week

    await streak_module.apply_checkin(db_session, habit, entry)

    assert calls == []  # not newly satisfied — nothing to do, not even a fallback
    assert habit.current_streak == 0
    assert habit.streak_last_counted_period_start is None


async def test_times_per_week_reaching_target_increments(db_session, monkeypatch):
    user = await _make_user(db_session, "checkin-tpw-full@example.com")
    monday = TODAY - timedelta(days=TODAY.weekday())
    habit = await _make_habit(
        db_session, user, FrequencyType.TIMES_PER_WEEK, {"target": 2}, monday - timedelta(weeks=2)
    )
    # last week already satisfied and counted
    await _add_and_flush_entry(db_session, habit, monday - timedelta(weeks=1))
    await _add_and_flush_entry(db_session, habit, monday - timedelta(weeks=1, days=-1))
    await db_session.commit()
    await streak_module.recompute(db_session, habit)
    await db_session.commit()
    assert habit.current_streak == 1

    calls = _spy_on_recompute(monkeypatch)
    await _add_and_flush_entry(db_session, habit, monday)  # 1 of 2 this week — not yet satisfied
    second_entry = await _add_and_flush_entry(db_session, habit, monday + timedelta(days=1))  # reaches target

    await streak_module.apply_checkin(db_session, habit, second_entry)

    assert calls == []  # contiguous with last week — fast path applies
    assert habit.current_streak == 2
    assert habit.streak_last_counted_period_start == monday
