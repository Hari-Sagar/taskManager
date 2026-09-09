from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from habit_tracker.jobs.scheduler import create_scheduler


def test_create_scheduler_registers_the_nightly_job():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    scheduler = create_scheduler(session_factory)

    job = scheduler.get_job("nightly_reconciliation")
    assert job is not None
