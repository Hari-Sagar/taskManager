async def test_list_returns_only_callers_habits(client, register_and_login):
    headers_a = await register_and_login("owner-a@example.com")
    headers_b = await register_and_login("owner-b@example.com")

    await client.post(
        "/api/v1/habits", headers=headers_a,
        json={"name": "A's habit", "frequency_type": "daily", "frequency_config": {}},
    )
    await client.post(
        "/api/v1/habits", headers=headers_b,
        json={"name": "B's habit", "frequency_type": "daily", "frequency_config": {}},
    )

    response = await client.get("/api/v1/habits", headers=headers_a)
    assert response.status_code == 200
    names = [h["name"] for h in response.json()]
    assert names == ["A's habit"]


async def test_list_excludes_archived_by_default(client, register_and_login):
    headers = await register_and_login("archiver@example.com")
    created = await client.post(
        "/api/v1/habits", headers=headers,
        json={"name": "Temp", "frequency_type": "daily", "frequency_config": {}},
    )
    habit_id = created.json()["id"]
    await client.delete(f"/api/v1/habits/{habit_id}", headers=headers)

    default_list = await client.get("/api/v1/habits", headers=headers)
    assert default_list.json() == []

    with_archived = await client.get("/api/v1/habits?include_archived=true", headers=headers)
    assert len(with_archived.json()) == 1


async def test_get_another_users_habit_returns_404(client, register_and_login):
    headers_a = await register_and_login("victim@example.com")
    headers_b = await register_and_login("attacker@example.com")

    created = await client.post(
        "/api/v1/habits", headers=headers_a,
        json={"name": "Private", "frequency_type": "daily", "frequency_config": {}},
    )
    habit_id = created.json()["id"]

    response = await client.get(f"/api/v1/habits/{habit_id}", headers=headers_b)
    assert response.status_code == 404
