from datetime import date, datetime
from zoneinfo import ZoneInfo

from habit_tracker.models.habit_schedule import FrequencyType, HabitSchedule
from habit_tracker.models.user import User
from habit_tracker.services.schedule import is_due_on, local_today, period_key


def _schedule(frequency_type, frequency_config):
    # Not persisted — is_due_on/period_key are pure functions over the
    # schedule's fields, no DB needed.
    return HabitSchedule(
        habit_id=1, frequency_type=frequency_type, frequency_config=frequency_config, effective_from=date(2026, 1, 1)
    )


def test_daily_habit_is_due_every_date():
    schedule = _schedule(FrequencyType.DAILY, {})
    for day in range(1, 8):
        assert is_due_on(schedule, date(2026, 1, day)) is True


def test_weekly_days_habit_due_only_on_configured_weekdays():
    # Monday=0, Wednesday=2, Friday=4
    schedule = _schedule(FrequencyType.WEEKLY_DAYS, {"days": [0, 2, 4]})

    monday = date(2026, 1, 5)  # a Monday
    for offset, expected in zip(range(7), [True, False, True, False, True, False, False]):
        assert is_due_on(schedule, monday.replace(day=monday.day + offset)) is expected


def test_times_per_week_is_due_every_day():
    schedule = _schedule(FrequencyType.TIMES_PER_WEEK, {"target": 3})
    for day in range(5, 12):
        assert is_due_on(schedule, date(2026, 1, day)) is True


def test_period_key_daily_and_weekly_days_is_the_date_itself():
    daily = _schedule(FrequencyType.DAILY, {})
    assert period_key(daily, date(2026, 1, 7)) == date(2026, 1, 7)


def test_times_per_week_period_key_same_within_week_different_across_boundary():
    schedule = _schedule(FrequencyType.TIMES_PER_WEEK, {"target": 3})

    monday = date(2026, 1, 5)
    wednesday = date(2026, 1, 7)
    sunday = date(2026, 1, 11)
    next_monday = date(2026, 1, 12)

    assert period_key(schedule, monday) == period_key(schedule, wednesday) == period_key(schedule, sunday)
    assert period_key(schedule, next_monday) != period_key(schedule, sunday)


def test_local_today_respects_timezone():
    user = User(email="tz@example.com", hashed_password="x", timezone="Asia/Tokyo", day_start_hour=0)
    # 2026-01-01 23:00 UTC is already 2026-01-02 in Tokyo (UTC+9)
    now = datetime(2026, 1, 1, 23, 0, tzinfo=ZoneInfo("UTC"))
    assert local_today(user, now=now) == date(2026, 1, 2)


def test_local_today_respects_day_start_hour_boundary():
    user = User(email="nightowl@example.com", hashed_password="x", timezone="UTC", day_start_hour=3)
    # 2:30am local is still "yesterday" when the day starts at 3am
    just_before_boundary = datetime(2026, 1, 2, 2, 30, tzinfo=ZoneInfo("UTC"))
    assert local_today(user, now=just_before_boundary) == date(2026, 1, 1)

    just_after_boundary = datetime(2026, 1, 2, 3, 30, tzinfo=ZoneInfo("UTC"))
    assert local_today(user, now=just_after_boundary) == date(2026, 1, 2)
