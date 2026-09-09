from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from habit_tracker.core.deps import get_current_user
from habit_tracker.db.session import get_db
from habit_tracker.models.user import User
from habit_tracker.schemas.settings import SettingsResponse, SettingsUpdate
from habit_tracker.services import settings as settings_service

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("", response_model=SettingsResponse)
async def get_settings(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    return await settings_service.get_settings(session, current_user)


@router.patch("", response_model=SettingsResponse)
async def update_settings(
    body: SettingsUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    return await settings_service.update_settings(session, current_user, body)
