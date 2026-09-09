from sqlalchemy.ext.asyncio import AsyncSession

from habit_tracker.models.notification_preference import NotificationPreference
from habit_tracker.models.user import User
from habit_tracker.schemas.settings import NotificationSettings, SettingsResponse, SettingsUpdate


async def _get_or_create_preference(session: AsyncSession, user: User) -> NotificationPreference:
    pref = await session.get(NotificationPreference, user.id)
    if pref is None:
        pref = NotificationPreference(user_id=user.id, enabled=False)
        session.add(pref)
        await session.commit()
        await session.refresh(pref)
    return pref


async def get_settings(session: AsyncSession, user: User) -> SettingsResponse:
    pref = await _get_or_create_preference(session, user)
    return SettingsResponse(
        timezone=user.timezone,
        day_start_hour=user.day_start_hour,
        notifications=NotificationSettings(enabled=pref.enabled, remind_local_time=pref.remind_local_time),
    )


async def update_settings(session: AsyncSession, user: User, data: SettingsUpdate) -> SettingsResponse:
    if data.timezone is not None:
        user.timezone = data.timezone
    if data.day_start_hour is not None:
        user.day_start_hour = data.day_start_hour

    if data.notifications is not None:
        pref = await _get_or_create_preference(session, user)
        if data.notifications.enabled is not None:
            pref.enabled = data.notifications.enabled
        if data.notifications.remind_local_time is not None:
            pref.remind_local_time = data.notifications.remind_local_time

    await session.commit()
    return await get_settings(session, user)
