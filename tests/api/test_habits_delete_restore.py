async def test_delete_archives_and_restore_clears_it(client, register_and_login):
    headers = await register_and_login("archive-restore@example.com")
    created = await client.post(
        "/api/v1/habits", headers=headers,
        json={"name": "Floss", "frequency_type": "daily", "frequency_config": {}},
    )
    habit_id = created.json()["id"]

    delete_response = await client.delete(f"/api/v1/habits/{habit_id}", headers=headers)
    assert delete_response.status_code == 204

    listed = await client.get("/api/v1/habits", headers=headers)
    assert listed.json() == []

    restore_response = await client.post(f"/api/v1/habits/{habit_id}/restore", headers=headers)
    assert restore_response.status_code == 200
    assert restore_response.json()["archived_at"] is None

    listed_again = await client.get("/api/v1/habits", headers=headers)
    assert len(listed_again.json()) == 1
