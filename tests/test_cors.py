from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from httpx import ASGITransport, AsyncClient

from habit_tracker.core.config import Settings


def test_cors_allowed_origins_list_parses_comma_separated_env_value():
    settings = Settings(cors_allowed_origins="https://a.example.com, https://b.example.com ,")
    assert settings.cors_allowed_origins_list == ["https://a.example.com", "https://b.example.com"]


def test_cors_allowed_origins_list_empty_by_default():
    settings = Settings(cors_allowed_origins="")
    assert settings.cors_allowed_origins_list == []


async def _cors_app(allowed_origins):
    """A minimal app wired with CORSMiddleware exactly as main.py wires
    the real one — isolates the test from the real app's settings
    singleton (which is fixed at process/import time) while testing the
    identical middleware configuration pattern."""
    app = FastAPI()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/ping")
    def ping():
        return {"ok": True}

    return app


async def test_allowed_origin_receives_the_acao_header():
    app = await _cors_app(["https://allowed.example.com"])
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/ping", headers={"Origin": "https://allowed.example.com"})

    assert response.headers.get("access-control-allow-origin") == "https://allowed.example.com"


async def test_disallowed_origin_does_not_receive_the_acao_header():
    app = await _cors_app(["https://allowed.example.com"])
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/ping", headers={"Origin": "https://not-allowed.example.com"})

    assert "access-control-allow-origin" not in response.headers


async def test_real_app_denies_cors_by_default(client):
    """The actual app, with its default (empty) allowed-origins list — no
    origin should ever get the header until an operator configures one."""
    response = await client.get("/health", headers={"Origin": "https://anything.example.com"})
    assert "access-control-allow-origin" not in response.headers
