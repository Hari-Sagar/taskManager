import sys
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """The Limiter's in-memory storage is a process-lifetime singleton
    (core/rate_limit.py) — without a reset, request counts would leak
    across unrelated test functions and cause order-dependent flakiness."""
    from habit_tracker.core.rate_limit import limiter

    limiter.reset()
    yield
    limiter.reset()


@pytest.fixture
def migrated_db(tmp_path):
    """Runs the real Alembic migrations against a fresh temp SQLite file.

    This is what item 3's acceptance test targets: the *migration*, not
    just `Base.metadata.create_all()`, creates the expected schema.
    """
    db_path = tmp_path / "test.db"
    database_url = f"sqlite+aiosqlite:///{db_path}"

    alembic_cfg = Config(str(REPO_ROOT / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(REPO_ROOT / "alembic"))
    alembic_cfg.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(alembic_cfg, "head")

    yield database_url


@pytest.fixture
async def db_session(migrated_db):
    engine = create_async_engine(migrated_db)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


@pytest.fixture
async def client(migrated_db):
    """An httpx AsyncClient wired to the real FastAPI app, with get_db
    overridden to hit the test's migrated temp DB instead of the app's
    configured one."""
    from habit_tracker.db.session import get_db
    from habit_tracker.main import app

    engine = create_async_engine(migrated_db)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async def _get_db_override():
        async with session_factory() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = _get_db_override
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
    await engine.dispose()


@pytest.fixture
def register_and_login(client):
    """Returns an async factory: await register_and_login("a@x.com") ->
    {"Authorization": "Bearer ..."} headers for a freshly registered user.
    Shared across every test module that needs an authenticated caller."""

    async def _factory(email="user@example.com", password="hunter22"):
        await client.post("/api/v1/auth/register", json={"email": email, "password": password})
        login = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
        token = login.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    return _factory
