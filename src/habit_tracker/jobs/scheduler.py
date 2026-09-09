"""The nightly job: catches passive streak breaks (a day/week elapsing
with no check-in — see ARCHITECTURE.md's "Streak design") and sends
reminder emails for habits still pending today. Shared infrastructure —
one daily pass covers both concerns.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from habit_tracker.models.habit import Habit
from habit_tracker.services import notifications as notifications_service
from habit_tracker.services import streak as streak_service


async def run_nightly_reconciliation(session: AsyncSession) -> None:
    """Runs reconcile() (frozen for archived habits, recomputed otherwise)
    over every habit, then commits once. Bounded per-habit cost via
    reconcile()/recompute(), not a single giant query."""
    result = await session.execute(select(Habit))
    for habit in result.scalars().all():
        await streak_service.reconcile(session, habit)
    await session.commit()


async def run_notification_sweep(session: AsyncSession) -> None:
    reminders = await notifications_service.get_pending_reminders(session)
    for user, habits in reminders:
        await notifications_service.send_reminder_email(user, habits)


def create_scheduler(session_factory: async_sessionmaker):
    """Wires both jobs into a daily APScheduler cron trigger. Not
    exercised by real clock ticks in tests — see run_nightly_reconciliation
    / run_notification_sweep above, which are what's actually tested."""
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

    scheduler = AsyncIOScheduler()

    async def _nightly_job():
        async with session_factory() as session:
            await run_nightly_reconciliation(session)
            await run_notification_sweep(session)

    scheduler.add_job(_nightly_job, "cron", hour=2, minute=0, id="nightly_reconciliation")
    return scheduler
