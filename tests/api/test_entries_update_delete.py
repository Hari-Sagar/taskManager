from datetime import date, timedelta

from sqlalchemy import select

from habit_tracker.models.habit_schedule import HabitSchedule

TODAY = date.today()


async def _create_daily_habit(client, headers, db_session):
    response = await client.post(
        "/api/v1/habits", headers=headers,
        json={"name": "Gym", "frequency_type": "daily", "frequency_config": {}},
    )
    habit_id = response.json()["id"]

    # Backdate the schedule so entries a few days in the past fall within
    # it — a habit created "just now" via the API can't otherwise have a
    # multi-day streak ending today (its own schedule wouldn't cover
    # yesterday). This mirrors a habit that's actually existed a while.
    result = await db_session.execute(select(HabitSchedule).where(HabitSchedule.habit_id == habit_id))
    schedule = result.scalar_one()
    schedule.effective_from = TODAY - timedelta(days=10)
    await db_session.commit()

    return habit_id


async def test_editing_a_past_entry_recomputes_counters_and_sets_edited_at(client, register_and_login, db_session):
    headers = await register_and_login("edit-recompute@example.com")
    habit_id = await _create_daily_habit(client, headers, db_session)

    # Build a 3-day streak: day-2, day-1, today.
    for offset in (2, 1, 0):
        d = (TODAY - timedelta(days=offset)).isoformat()
        await client.post(f"/api/v1/habits/{habit_id}/entries", headers=headers, json={"local_date": d, "status": "done"})

    habit = (await client.get(f"/api/v1/habits/{habit_id}", headers=headers)).json()
    assert habit["current_streak"] == 3

    # Flip the middle day to "skipped" — should break the streak down to 1 (today only).
    middle = (TODAY - timedelta(days=1)).isoformat()
    patch_response = await client.patch(
        f"/api/v1/habits/{habit_id}/entries/{middle}", headers=headers, json={"status": "skipped"}
    )
    assert patch_response.status_code == 200
    assert patch_response.json()["edited_at"] is not None

    habit_after = (await client.get(f"/api/v1/habits/{habit_id}", headers=headers)).json()
    assert habit_after["current_streak"] == 1


async def test_deleting_a_past_entry_recomputes_counters(client, register_and_login, db_session):
    headers = await register_and_login("delete-recompute@example.com")
    habit_id = await _create_daily_habit(client, headers, db_session)

    for offset in (2, 1, 0):
        d = (TODAY - timedelta(days=offset)).isoformat()
        await client.post(f"/api/v1/habits/{habit_id}/entries", headers=headers, json={"local_date": d, "status": "done"})

    middle = (TODAY - timedelta(days=1)).isoformat()
    delete_response = await client.delete(f"/api/v1/habits/{habit_id}/entries/{middle}", headers=headers)
    assert delete_response.status_code == 204

    habit_after = (await client.get(f"/api/v1/habits/{habit_id}", headers=headers)).json()
    assert habit_after["current_streak"] == 1


async def test_patch_unknown_entry_returns_404(client, register_and_login, db_session):
    headers = await register_and_login("edit-missing@example.com")
    habit_id = await _create_daily_habit(client, headers, db_session)

    response = await client.patch(
        f"/api/v1/habits/{habit_id}/entries/2020-01-01", headers=headers, json={"status": "skipped"}
    )
    assert response.status_code == 404
