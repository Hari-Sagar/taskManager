async def _create_habit(client, headers, **overrides):
    payload = {"name": "Meditate", "frequency_type": "daily", "frequency_config": {}}
    payload.update(overrides)
    response = await client.post("/api/v1/habits", headers=headers, json=payload)
    return response.json()["id"]


async def test_create_entry_defaults_to_today(client, register_and_login):
    headers = await register_and_login("entry-creator@example.com")
    habit_id = await _create_habit(client, headers)

    response = await client.post(
        f"/api/v1/habits/{habit_id}/entries", headers=headers, json={"status": "done"}
    )
    assert response.status_code == 201
    body = response.json()
    assert body["habit_id"] == habit_id
    assert body["local_date"]  # defaulted, non-empty
    assert body["status"] == "done"


async def test_duplicate_habit_local_date_returns_409(client, register_and_login):
    headers = await register_and_login("entry-dupe@example.com")
    habit_id = await _create_habit(client, headers)

    first = await client.post(
        f"/api/v1/habits/{habit_id}/entries", headers=headers, json={"local_date": "2026-01-05", "status": "done"}
    )
    assert first.status_code == 201

    second = await client.post(
        f"/api/v1/habits/{habit_id}/entries", headers=headers, json={"local_date": "2026-01-05", "status": "done"}
    )
    assert second.status_code == 409
