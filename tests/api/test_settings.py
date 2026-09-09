async def test_get_settings_returns_defaults(client, register_and_login):
    headers = await register_and_login("settings-default@example.com")
    response = await client.get("/api/v1/settings", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["timezone"] == "UTC"
    assert body["day_start_hour"] == 0
    assert body["notifications"] == {"enabled": False, "remind_local_time": None}


async def test_patch_updates_timezone_day_start_hour_and_notifications(client, register_and_login):
    headers = await register_and_login("settings-patch@example.com")

    response = await client.patch(
        "/api/v1/settings",
        headers=headers,
        json={
            "timezone": "America/Los_Angeles",
            "day_start_hour": 3,
            "notifications": {"enabled": True, "remind_local_time": "20:00:00"},
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["timezone"] == "America/Los_Angeles"
    assert body["day_start_hour"] == 3
    assert body["notifications"]["enabled"] is True
    assert body["notifications"]["remind_local_time"] == "20:00:00"

    # GET reflects the same values afterward
    get_response = await client.get("/api/v1/settings", headers=headers)
    assert get_response.json() == body


async def test_invalid_timezone_returns_422(client, register_and_login):
    headers = await register_and_login("settings-bad-tz@example.com")
    response = await client.patch("/api/v1/settings", headers=headers, json={"timezone": "Not/A_Real_Zone"})
    assert response.status_code == 422
