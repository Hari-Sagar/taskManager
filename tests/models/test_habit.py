from habit_tracker.models.habit import Habit
from habit_tracker.models.user import User


async def test_habit_defaults_for_streak_columns(db_session):
    """PLAN.md item 5 acceptance: inserting a habit with only required
    fields leaves streak columns at their defaults (0, 0, null)."""
    user = User(email="habit-owner@example.com", hashed_password="x")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    habit = Habit(user_id=user.id, name="Meditate")
    db_session.add(habit)
    await db_session.commit()
    await db_session.refresh(habit)

    assert habit.current_streak == 0
    assert habit.longest_streak == 0
    assert habit.streak_last_counted_period_start is None
    assert habit.archived_at is None
