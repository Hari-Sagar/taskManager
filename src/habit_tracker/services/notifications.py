"""Reminder selection + delivery. Selection (who to notify) and delivery
(how the email gets sent) are kept as separate functions on purpose —
ARCHITECTURE.md scopes notifications as "email only", and delivery is the
part that needs real SMTP infrastructure and is what tests mock out."""

import smtplib
from email.message import EmailMessage
from typing import List, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from habit_tracker.core.config import settings
from habit_tracker.models.entry import Entry
from habit_tracker.models.habit import Habit
from habit_tracker.models.notification_preference import NotificationPreference
from habit_tracker.models.user import User
from habit_tracker.services.schedule import active_schedule_as_of, is_due_on, local_today


async def get_pending_reminders(session: AsyncSession) -> List[Tuple[User, List[Habit]]]:
    """Users with notifications enabled who have at least one non-archived
    habit due today with no entry yet."""
    result = await session.execute(
        select(User)
        .join(NotificationPreference, NotificationPreference.user_id == User.id)
        .where(NotificationPreference.enabled.is_(True))
    )
    users = result.scalars().all()

    reminders = []
    for user in users:
        today = local_today(user)
        habits_result = await session.execute(
            select(Habit).where(Habit.user_id == user.id, Habit.archived_at.is_(None))
        )

        due_without_entry = []
        for habit in habits_result.scalars().all():
            schedule = await active_schedule_as_of(session, habit.id, today)
            if schedule is None or not is_due_on(schedule, today):
                continue

            entry_result = await session.execute(
                select(Entry).where(Entry.habit_id == habit.id, Entry.local_date == today)
            )
            if entry_result.scalar_one_or_none() is None:
                due_without_entry.append(habit)

        if due_without_entry:
            reminders.append((user, due_without_entry))

    return reminders


def _build_message(user: User, habits: List[Habit]) -> EmailMessage:
    msg = EmailMessage()
    msg["Subject"] = "Habit reminder"
    msg["From"] = settings.smtp_from_address
    msg["To"] = user.email
    habit_names = ", ".join(h.name for h in habits)
    msg.set_content(f"You haven't checked in today for: {habit_names}")
    return msg


async def send_reminder_email(user: User, habits: List[Habit]) -> None:
    """Real delivery — deliberately the one piece of this module that
    talks to the network, so tests can mock exactly this function."""
    message = _build_message(user, habits)
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
        if settings.smtp_username:
            server.starttls()
            server.login(settings.smtp_username, settings.smtp_password)
        server.send_message(message)
