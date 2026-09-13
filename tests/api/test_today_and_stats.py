from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from habit_tracker.models.habit_schedule import HabitSchedule
from habit_tracker.services import streak as streak_module

# See test_entries_update_delete.py — UTC, not local date.today(), to
# match local_today() for these UTC-timezone test users.
TODAY = datetime.now(timezone.utc).date()


async def test_today_returns_due_habits_with_status_and_streak(client, register_and_login):
    headers = await register_and_login("today-user@example.com")

    daily = await client.post(
        "/api/v1/habits", headers=headers, json={"name": "Daily", "frequency_type": "daily", "frequency_config": {}}
    )
    daily_id = daily.json()["id"]

    # A habit scheduled only on a weekday that is NOT today should be absent.
    not_today_weekday = (TODAY.weekday() + 1) % 7
    off_day = await client.post(
        "/api/v1/habits", headers=headers,
        json={"name": "Not today", "frequency_type": "weekly_days", "frequency_config": {"days": [not_today_weekday]}},
    )

    await client.post(f"/api/v1/habits/{daily_id}/entries", headers=headers, json={"status": "done"})

    response = await client.get("/api/v1/today", headers=headers)
    assert response.status_code == 200
    items = response.json()

    names = {item["name"] for item in items}
    assert "Daily" in names
    assert "Not today" not in names

    daily_item = next(item for item in items if item["habit_id"] == daily_id)
    assert daily_item["status"] == "done"
    assert daily_item["current_streak"] == 1


async def test_today_excludes_archived_habits(client, register_and_login):
    headers = await register_and_login("today-archived@example.com")
    created = await client.post(
        "/api/v1/habits", headers=headers, json={"name": "Archived", "frequency_type": "daily", "frequency_config": {}}
    )
    habit_id = created.json()["id"]
    await client.delete(f"/api/v1/habits/{habit_id}", headers=headers)

    response = await client.get("/api/v1/today", headers=headers)
    assert response.json() == []


async def test_today_never_calls_recompute_or_apply_checkin(client, register_and_login, monkeypatch):
    async def boom(*args, **kwargs):
        raise AssertionError("today should never trigger streak recomputation")

    monkeypatch.setattr(streak_module, "recompute", boom)
    monkeypatch.setattr(streak_module, "apply_checkin", boom)

    headers = await register_and_login("today-no-recompute@example.com")
    await client.post("/api/v1/habits", headers=headers, json={"name": "X", "frequency_type": "daily", "frequency_config": {}})

    response = await client.get("/api/v1/today", headers=headers)
    assert response.status_code == 200


async def test_pending_status_when_not_yet_checked_in(client, register_and_login):
    headers = await register_and_login("today-pending@example.com")
    await client.post("/api/v1/habits", headers=headers, json={"name": "Y", "frequency_type": "daily", "frequency_config": {}})

    response = await client.get("/api/v1/today", headers=headers)
    assert response.json()[0]["status"] == "pending"


async def test_stats_endpoint_matches_habit_row(client, register_and_login, db_session):
    headers = await register_and_login("stats-user@example.com")
    created = await client.post(
        "/api/v1/habits", headers=headers, json={"name": "Stats", "frequency_type": "daily", "frequency_config": {}}
    )
    habit_id = created.json()["id"]

    result = await db_session.execute(select(HabitSchedule).where(HabitSchedule.habit_id == habit_id))
    schedule = result.scalar_one()
    schedule.effective_from = TODAY - timedelta(days=5)
    await db_session.commit()

    for offset in (1, 0):
        d = (TODAY - timedelta(days=offset)).isoformat()
        await client.post(f"/api/v1/habits/{habit_id}/entries", headers=headers, json={"local_date": d, "status": "done"})

    response = await client.get(f"/api/v1/habits/{habit_id}/stats", headers=headers)
    assert response.status_code == 200
    assert response.json() == {"current_streak": 2, "longest_streak": 2}


async def test_stats_for_unknown_habit_returns_404(client, register_and_login):
    headers = await register_and_login("stats-missing@example.com")
    response = await client.get("/api/v1/habits/999999/stats", headers=headers)
    assert response.status_code == 404
