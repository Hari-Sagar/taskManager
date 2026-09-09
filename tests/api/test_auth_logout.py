async def test_logout_then_refresh_returns_401(client):
    await client.post("/api/v1/auth/register", json={"email": "logout@example.com", "password": "hunter22"})
    login = await client.post("/api/v1/auth/login", json={"email": "logout@example.com", "password": "hunter22"})
    refresh_token = login.json()["refresh_token"]

    logout_response = await client.post("/api/v1/auth/logout", json={"refresh_token": refresh_token})
    assert logout_response.status_code == 204

    reused = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert reused.status_code == 401
