from datetime import date, datetime, timedelta, timezone
from unittest.mock import AsyncMock

from habit_tracker.models.entry import Entry, EntryStatus
from habit_tracker.models.habit import Habit
from habit_tracker.models.habit_schedule import FrequencyType, HabitSchedule
from habit_tracker.models.notification_preference import NotificationPreference
from habit_tracker.models.user import User
from habit_tracker.services import notifications as notifications_module
from habit_tracker.services.notifications import get_pending_reminders

TODAY = date.today()


async def _make_user(db_session, email, notifications_enabled):
    user = User(email=email, hashed_password="x", timezone="UTC", day_start_hour=0)
    db_session.add(user)
    await db_session.flush()
    db_session.add(NotificationPreference(user_id=user.id, enabled=notifications_enabled))
    await db_session.commit()
    await db_session.refresh(user)
    return user


async def _make_habit(db_session, user, effective_from):
    habit = Habit(user_id=user.id, name="Meditate")
    db_session.add(habit)
    await db_session.flush()
    db_session.add(
        HabitSchedule(habit_id=habit.id, frequency_type=FrequencyType.DAILY, frequency_config={}, effective_from=effective_from)
    )
    await db_session.commit()
    await db_session.refresh(habit)
    return habit


async def test_only_enabled_users_with_pending_habits_are_selected(db_session):
    enabled_user = await _make_user(db_session, "enabled@example.com", notifications_enabled=True)
    pending_habit = await _make_habit(db_session, enabled_user, TODAY - timedelta(days=5))

    disabled_user = await _make_user(db_session, "disabled@example.com", notifications_enabled=False)
    await _make_habit(db_session, disabled_user, TODAY - timedelta(days=5))

    reminders = await get_pending_reminders(db_session)

    assert len(reminders) == 1
    user, habits = reminders[0]
    assert user.email == "enabled@example.com"
    assert [h.id for h in habits] == [pending_habit.id]


async def test_habit_already_checked_in_today_is_excluded(db_session):
    user = await _make_user(db_session, "already-done@example.com", notifications_enabled=True)
    habit = await _make_habit(db_session, user, TODAY - timedelta(days=5))
    db_session.add(
        Entry(habit_id=habit.id, local_date=TODAY, completed_at=datetime.now(timezone.utc), status=EntryStatus.DONE)
    )
    await db_session.commit()

    reminders = await get_pending_reminders(db_session)

    assert reminders == []


async def test_send_reminder_email_is_mocked_not_exercised_for_real(db_session, monkeypatch):
    user = await _make_user(db_session, "mocked-send@example.com", notifications_enabled=True)
    await _make_habit(db_session, user, TODAY - timedelta(days=5))

    mock_send = AsyncMock()
    monkeypatch.setattr(notifications_module, "send_reminder_email", mock_send)

    reminders = await get_pending_reminders(db_session)
    for reminder_user, habits in reminders:
        await notifications_module.send_reminder_email(reminder_user, habits)

    mock_send.assert_awaited_once()
    called_user, called_habits = mock_send.call_args.args
    assert called_user.email == "mocked-send@example.com"
    assert len(called_habits) == 1
