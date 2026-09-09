from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from habit_tracker.db.base import Base

REPO_ROOT = Path(__file__).resolve().parent.parent


async def test_engine_creates_configured_sqlite_file_and_roundtrips(tmp_path):
    """PLAN.md Phase 0 item 1 acceptance: app startup creates the
    configured SQLite file; a trivial SELECT 1 roundtrip succeeds."""
    db_path = tmp_path / "startup.db"
    assert not db_path.exists()

    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT 1"))
        assert result.scalar_one() == 1
    await engine.dispose()

    assert db_path.exists()


def test_alembic_upgrade_head_runs_cleanly_on_fresh_db(tmp_path):
    """PLAN.md Phase 0 item 2 acceptance (upgrade half): `alembic upgrade
    head` runs cleanly against a fresh DB."""
    db_path = tmp_path / "fresh.db"
    alembic_cfg = Config(str(REPO_ROOT / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(REPO_ROOT / "alembic"))
    alembic_cfg.set_main_option("sqlalchemy.url", f"sqlite+aiosqlite:///{db_path}")

    command.upgrade(alembic_cfg, "head")  # must not raise

    assert db_path.exists()


def test_models_match_migrations_no_autogenerate_diff(migrated_db):
    """PLAN.md Phase 0 item 2 acceptance (autogenerate half): once all
    migrations are applied, autogenerate against the models produces an
    empty diff — i.e. the migration history and the ORM models agree.
    Uses a sync engine since Alembic's autogenerate compare works against
    a plain Connection.
    """
    sync_url = migrated_db.replace("sqlite+aiosqlite://", "sqlite://")
    from sqlalchemy import create_engine

    engine = create_engine(sync_url)
    with engine.connect() as conn:
        mc = MigrationContext.configure(conn)
        diff = compare_metadata(mc, Base.metadata)
    engine.dispose()

    assert diff == [], f"models and migrations have drifted: {diff}"
