async def test_patch_non_frequency_fields_persist(client, register_and_login):
    headers = await register_and_login("patcher@example.com")
    created = await client.post(
        "/api/v1/habits", headers=headers,
        json={"name": "Old name", "frequency_type": "daily", "frequency_config": {}},
    )
    habit_id = created.json()["id"]

    response = await client.patch(
        f"/api/v1/habits/{habit_id}", headers=headers, json={"name": "New name", "description": "desc"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "New name"
    assert body["description"] == "desc"


async def test_patch_frequency_change_appends_new_schedule(client, register_and_login, db_session):
    from datetime import date, timedelta

    from sqlalchemy import select

    from habit_tracker.models.habit_schedule import HabitSchedule
    from habit_tracker.services.schedule import active_schedule_as_of

    headers = await register_and_login("schedule-patcher@example.com")
    created = await client.post(
        "/api/v1/habits", headers=headers,
        json={"name": "Gym", "frequency_type": "daily", "frequency_config": {}},
    )
    habit_id = created.json()["id"]

    response = await client.patch(
        f"/api/v1/habits/{habit_id}",
        headers=headers,
        json={"frequency_type": "times_per_week", "frequency_config": {"target": 3}},
    )
    assert response.status_code == 200

    result = await db_session.execute(
        select(HabitSchedule).where(HabitSchedule.habit_id == habit_id).order_by(HabitSchedule.id)
    )
    schedules = result.scalars().all()
    assert len(schedules) == 2
    assert schedules[0].frequency_type.value == "daily"
    assert schedules[1].frequency_type.value == "times_per_week"
    # both rows share today's effective_from — the PATCH happened
    # immediately after creation in this test, same as any same-day edit
    # in real use. Resolution must still deterministically prefer the
    # newer row rather than depend on undefined ordering.
    assert schedules[0].effective_from == schedules[1].effective_from

    active_today = await active_schedule_as_of(db_session, habit_id, schedules[1].effective_from)
    assert active_today.id == schedules[1].id  # the newer row wins the same-day tie

    # a genuinely earlier date still resolves to nothing (habit didn't exist yet)
    earlier = schedules[1].effective_from - timedelta(days=365)
    assert await active_schedule_as_of(db_session, habit_id, earlier) is None


async def test_patch_frequency_type_without_config_is_rejected(client, register_and_login):
    headers = await register_and_login("half-patch@example.com")
    created = await client.post(
        "/api/v1/habits", headers=headers,
        json={"name": "Gym", "frequency_type": "daily", "frequency_config": {}},
    )
    habit_id = created.json()["id"]

    response = await client.patch(
        f"/api/v1/habits/{habit_id}", headers=headers, json={"frequency_type": "daily"}
    )
    assert response.status_code == 422
