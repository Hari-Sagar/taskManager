from datetime import date

from habit_tracker.models.habit import Habit
from habit_tracker.models.habit_schedule import FrequencyType, HabitSchedule
from habit_tracker.models.user import User
from habit_tracker.services.schedule import active_schedule_as_of as _active_schedule_as_of


async def test_two_schedule_versions_resolve_correctly_by_date(db_session):
    """PLAN.md item 6 acceptance: two schedule rows for one habit with
    different effective_from dates both insert; a helper query for
    "active schedule as of date X" returns the correct row when dates
    overlap."""
    user = User(email="schedule-owner@example.com", hashed_password="x")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    habit = Habit(user_id=user.id, name="Gym")
    db_session.add(habit)
    await db_session.commit()
    await db_session.refresh(habit)

    old_schedule = HabitSchedule(
        habit_id=habit.id,
        frequency_type=FrequencyType.DAILY,
        frequency_config={},
        effective_from=date(2026, 1, 1),
    )
    new_schedule = HabitSchedule(
        habit_id=habit.id,
        frequency_type=FrequencyType.TIMES_PER_WEEK,
        frequency_config={"target": 3},
        effective_from=date(2026, 6, 1),
    )
    db_session.add_all([old_schedule, new_schedule])
    await db_session.commit()

    before_switch = await _active_schedule_as_of(db_session, habit.id, date(2026, 5, 31))
    assert before_switch.frequency_type == FrequencyType.DAILY

    after_switch = await _active_schedule_as_of(db_session, habit.id, date(2026, 6, 1))
    assert after_switch.frequency_type == FrequencyType.TIMES_PER_WEEK

    long_after = await _active_schedule_as_of(db_session, habit.id, date(2026, 12, 31))
    assert long_after.frequency_type == FrequencyType.TIMES_PER_WEEK
