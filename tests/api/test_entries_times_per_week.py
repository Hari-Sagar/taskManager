from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from habit_tracker.models.habit_schedule import HabitSchedule

# See test_entries_update_delete.py — UTC, not local date.today(), to
# match local_today() for these UTC-timezone test users.
TODAY = datetime.now(timezone.utc).date()
MONDAY = TODAY - timedelta(days=TODAY.weekday())


async def _create_times_per_week_habit(client, headers, db_session, target=3, weeks_old=3):
    response = await client.post(
        "/api/v1/habits", headers=headers,
        json={"name": "Gym", "frequency_type": "times_per_week", "frequency_config": {"target": target}},
    )
    habit_id = response.json()["id"]

    result = await db_session.execute(select(HabitSchedule).where(HabitSchedule.habit_id == habit_id))
    schedule = result.scalar_one()
    schedule.effective_from = MONDAY - timedelta(weeks=weeks_old)
    await db_session.commit()

    return habit_id


async def _checkin(client, headers, habit_id, local_date):
    return await client.post(
        f"/api/v1/habits/{habit_id}/entries", headers=headers, json={"local_date": local_date.isoformat(), "status": "done"}
    )


async def test_only_reaches_done_once_target_met_and_streak_counts_weeks_not_entries(client, register_and_login, db_session):
    headers = await register_and_login("tpw-integration@example.com")
    habit_id = await _create_times_per_week_habit(client, headers, db_session, target=3, weeks_old=2)

    last_week = MONDAY - timedelta(weeks=1)

    # Last week: 2 check-ins — under target, should not count as a streak yet.
    await _checkin(client, headers, habit_id, last_week)
    await _checkin(client, headers, habit_id, last_week + timedelta(days=1))
    habit = (await client.get(f"/api/v1/habits/{habit_id}", headers=headers)).json()
    assert habit["current_streak"] == 0

    # The 3rd check-in reaches target — now last week counts as one satisfied period.
    response = await _checkin(client, headers, habit_id, last_week + timedelta(days=2))
    assert response.status_code == 201
    habit = (await client.get(f"/api/v1/habits/{habit_id}", headers=headers)).json()
    assert habit["current_streak"] == 1

    # A 4th check-in the same week (already satisfied) must not double-count.
    await _checkin(client, headers, habit_id, last_week + timedelta(days=3))
    habit = (await client.get(f"/api/v1/habits/{habit_id}", headers=headers)).json()
    assert habit["current_streak"] == 1

    # This week: reach target too — streak becomes 2 (two satisfied weeks), not "6 entries".
    await _checkin(client, headers, habit_id, MONDAY)
    await _checkin(client, headers, habit_id, MONDAY + timedelta(days=1))
    response = await _checkin(client, headers, habit_id, MONDAY + timedelta(days=2))
    assert response.status_code == 201
    habit = (await client.get(f"/api/v1/habits/{habit_id}", headers=headers)).json()
    assert habit["current_streak"] == 2
