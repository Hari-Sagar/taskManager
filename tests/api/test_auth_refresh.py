async def test_refresh_rotates_token_and_invalidates_old_one(client):
    await client.post("/api/v1/auth/register", json={"email": "refresh@example.com", "password": "hunter22"})
    login = await client.post("/api/v1/auth/login", json={"email": "refresh@example.com", "password": "hunter22"})
    old_refresh_token = login.json()["refresh_token"]

    refreshed = await client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh_token})
    assert refreshed.status_code == 200
    new_body = refreshed.json()
    assert new_body["refresh_token"] != old_refresh_token

    # the old refresh token must no longer work
    reused = await client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh_token})
    assert reused.status_code == 401


async def test_refresh_with_garbage_token_returns_401(client):
    response = await client.post("/api/v1/auth/refresh", json={"refresh_token": "not-a-real-token"})
    assert response.status_code == 401
