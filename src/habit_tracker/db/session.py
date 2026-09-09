from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from habit_tracker.core.config import settings

engine = create_async_engine(settings.database_url)
async_session_factory = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncSession:
    async with async_session_factory() as session:
        try:
            yield session
        except Exception:
            # An unhandled error partway through a request must not leave a
            # half-committed transaction — see ARCHITECTURE.md's "Transaction
            # boundary" (entry insert + streak counter update roll back together).
            await session.rollback()
            raise
