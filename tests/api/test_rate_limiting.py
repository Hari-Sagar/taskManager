async def test_login_rate_limit_returns_429_once_exceeded(client):
    # Register directly (not via the register_and_login fixture, which
    # itself performs one login call) so the count below is exact.
    await client.post(
        "/api/v1/auth/register", json={"email": "rate-limit-login@example.com", "password": "hunter22"}
    )

    responses = []
    for _ in range(11):  # limit is 10/minute
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "rate-limit-login@example.com", "password": "hunter22"},
        )
        responses.append(response.status_code)

    assert responses[:10] == [200] * 10
    assert responses[10] == 429


async def test_login_under_the_limit_succeeds_normally(client, register_and_login):
    await register_and_login("rate-limit-login-ok@example.com")

    for _ in range(3):
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "rate-limit-login-ok@example.com", "password": "hunter22"},
        )
        assert response.status_code == 200


async def test_checkin_rate_limit_returns_429_once_exceeded(client, register_and_login):
    headers = await register_and_login("rate-limit-checkin@example.com")
    created = await client.post(
        "/api/v1/habits", headers=headers, json={"name": "Spam test", "frequency_type": "daily", "frequency_config": {}}
    )
    habit_id = created.json()["id"]

    statuses = []
    for i in range(21):  # limit is 20/minute; duplicate dates would 409 before 429, so use distinct dates
        from datetime import date, timedelta

        d = (date(2020, 1, 1) + timedelta(days=i)).isoformat()
        response = await client.post(
            f"/api/v1/habits/{habit_id}/entries", headers=headers, json={"local_date": d, "status": "done"}
        )
        statuses.append(response.status_code)

    assert statuses[:20] == [201] * 20
    assert statuses[20] == 429
