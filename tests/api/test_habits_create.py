async def test_create_habit_creates_habit_and_first_schedule(client, register_and_login):
    headers = await register_and_login("create@example.com")

    response = await client.post(
        "/api/v1/habits",
        headers=headers,
        json={"name": "Meditate", "frequency_type": "daily", "frequency_config": {}},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Meditate"
    assert body["current_streak"] == 0
    assert body["longest_streak"] == 0
    assert body["archived_at"] is None
