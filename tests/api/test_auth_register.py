async def test_register_returns_201_with_user_and_no_password(client):
    response = await client.post(
        "/api/v1/auth/register", json={"email": "new@example.com", "password": "hunter22"}
    )
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "new@example.com"
    assert "password" not in body
    assert "hashed_password" not in body
    assert "id" in body and "created_at" in body


async def test_register_duplicate_email_returns_409(client):
    payload = {"email": "dupe@example.com", "password": "hunter22"}
    first = await client.post("/api/v1/auth/register", json=payload)
    assert first.status_code == 201

    second = await client.post("/api/v1/auth/register", json=payload)
    assert second.status_code == 409
