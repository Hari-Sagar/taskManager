from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from habit_tracker.models.habit_schedule import HabitSchedule

# See test_entries_update_delete.py — UTC, not local date.today(), to
# match local_today() for these UTC-timezone test users.
TODAY = datetime.now(timezone.utc).date()


async def _create_habit_with_history(client, headers, db_session, name="Gym"):
    created = await client.post(
        "/api/v1/habits", headers=headers,
        json={"name": name, "frequency_type": "daily", "frequency_config": {}},
    )
    habit_id = created.json()["id"]

    result = await db_session.execute(select(HabitSchedule).where(HabitSchedule.habit_id == habit_id))
    schedule = result.scalar_one()
    schedule.effective_from = TODAY - timedelta(days=10)
    await db_session.commit()

    for offset in (2, 1, 0):
        d = (TODAY - timedelta(days=offset)).isoformat()
        await client.post(f"/api/v1/habits/{habit_id}/entries", headers=headers, json={"local_date": d, "status": "done"})

    return habit_id


async def test_export_contains_only_callers_data_and_excludes_streak_fields(client, register_and_login, db_session):
    headers_a = await register_and_login("export-owner@example.com")
    await _create_habit_with_history(client, headers_a, db_session, name="Gym")

    headers_b = await register_and_login("export-other@example.com")
    await _create_habit_with_history(client, headers_b, db_session, name="Someone else's habit")

    response = await client.get("/api/v1/export", headers=headers_a)
    assert response.status_code == 200
    body = response.json()

    assert len(body["habits"]) == 1
    assert body["habits"][0]["name"] == "Gym"
    assert "current_streak" not in body["habits"][0]
    assert "longest_streak" not in body["habits"][0]
    assert len(body["schedules"]) == 1
    assert len(body["entries"]) == 3


async def test_import_creates_new_habit_and_matches_recompute(client, register_and_login, db_session):
    headers_source = await register_and_login("import-source@example.com")
    await _create_habit_with_history(client, headers_source, db_session, name="Meditate")
    export_response = await client.get("/api/v1/export", headers=headers_source)
    payload = export_response.json()

    headers_dest = await register_and_login("import-dest@example.com")
    import_response = await client.post("/api/v1/import", headers=headers_dest, json=payload)
    assert import_response.status_code == 200
    result = import_response.json()
    assert result["imported"] == {"habits": 1, "entries": 3}
    assert result["skipped"] == {"habits": 0, "entries": 0}

    habits = (await client.get("/api/v1/habits", headers=headers_dest)).json()
    assert len(habits) == 1
    assert habits[0]["current_streak"] == 3  # matches what recompute() would produce for 3 consecutive days


async def test_reimporting_the_same_payload_skips_everything(client, register_and_login, db_session):
    headers_source = await register_and_login("reimport-source@example.com")
    await _create_habit_with_history(client, headers_source, db_session, name="Read")
    payload = (await client.get("/api/v1/export", headers=headers_source)).json()

    headers_dest = await register_and_login("reimport-dest@example.com")
    await client.post("/api/v1/import", headers=headers_dest, json=payload)

    second_response = await client.post("/api/v1/import", headers=headers_dest, json=payload)
    result = second_response.json()
    assert result["imported"] == {"habits": 0, "entries": 0}
    assert result["skipped"] == {"habits": 1, "entries": 3}
