async def test_me_without_token_returns_401(client):
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401


async def test_me_with_invalid_token_returns_401(client):
    response = await client.get("/api/v1/auth/me", headers={"Authorization": "Bearer not-a-real-token"})
    assert response.status_code == 401


async def test_me_with_valid_token_returns_correct_user(client):
    await client.post("/api/v1/auth/register", json={"email": "me@example.com", "password": "hunter22"})
    login = await client.post("/api/v1/auth/login", json={"email": "me@example.com", "password": "hunter22"})
    access_token = login.json()["access_token"]

    response = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {access_token}"})
    assert response.status_code == 200
    assert response.json()["email"] == "me@example.com"
