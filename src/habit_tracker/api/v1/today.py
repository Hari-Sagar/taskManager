from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from habit_tracker.core.deps import get_current_user
from habit_tracker.db.session import get_db
from habit_tracker.models.user import User
from habit_tracker.schemas.today import TodayItem
from habit_tracker.services import today as today_service

router = APIRouter(tags=["Today"])


@router.get("/today", response_model=list[TodayItem])
async def get_today(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Everything due today, with its status (done/skipped/pending) and
    current streak — the "home screen" view."""
    return await today_service.get_today(session, current_user)
