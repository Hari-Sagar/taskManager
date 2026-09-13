async def test_below_target_is_stored_but_not_counted_as_done(client, register_and_login):
    headers = await register_and_login("quant-below@example.com")
    created = await client.post(
        "/api/v1/habits", headers=headers,
        json={"name": "Water", "unit": "glasses", "target_value": 8, "frequency_type": "daily", "frequency_config": {}},
    )
    habit_id = created.json()["id"]

    response = await client.post(
        f"/api/v1/habits/{habit_id}/entries", headers=headers, json={"status": "done", "value": 3}
    )
    assert response.status_code == 201
    assert response.json()["value"] == 3  # stored as-is, for display/history

    habit = (await client.get(f"/api/v1/habits/{habit_id}", headers=headers)).json()
    assert habit["current_streak"] == 0


async def test_meeting_target_counts_as_done(client, register_and_login):
    headers = await register_and_login("quant-meets@example.com")
    created = await client.post(
        "/api/v1/habits", headers=headers,
        json={"name": "Water", "unit": "glasses", "target_value": 8, "frequency_type": "daily", "frequency_config": {}},
    )
    habit_id = created.json()["id"]

    response = await client.post(
        f"/api/v1/habits/{habit_id}/entries", headers=headers, json={"status": "done", "value": 8}
    )
    assert response.status_code == 201

    habit = (await client.get(f"/api/v1/habits/{habit_id}", headers=headers)).json()
    assert habit["current_streak"] == 1


async def test_exceeding_target_also_counts_as_done(client, register_and_login):
    headers = await register_and_login("quant-exceeds@example.com")
    created = await client.post(
        "/api/v1/habits", headers=headers,
        json={"name": "Pushups", "unit": "reps", "target_value": 20, "frequency_type": "daily", "frequency_config": {}},
    )
    habit_id = created.json()["id"]

    response = await client.post(
        f"/api/v1/habits/{habit_id}/entries", headers=headers, json={"status": "done", "value": 50}
    )
    assert response.status_code == 201

    habit = (await client.get(f"/api/v1/habits/{habit_id}", headers=headers)).json()
    assert habit["current_streak"] == 1
