async def test_login_correct_credentials_returns_token_pair(client):
    await client.post("/api/v1/auth/register", json={"email": "login@example.com", "password": "hunter22"})

    response = await client.post(
        "/api/v1/auth/login", json={"email": "login@example.com", "password": "hunter22"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["token_type"] == "bearer"


async def test_login_wrong_password_returns_401(client):
    await client.post("/api/v1/auth/register", json={"email": "login2@example.com", "password": "hunter22"})

    response = await client.post(
        "/api/v1/auth/login", json={"email": "login2@example.com", "password": "wrong-password"}
    )
    assert response.status_code == 401
