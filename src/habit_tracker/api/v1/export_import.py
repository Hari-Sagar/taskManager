from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from habit_tracker.core.deps import get_current_user
from habit_tracker.db.session import get_db
from habit_tracker.models.user import User
from habit_tracker.schemas.export_import import ExportPayload, ImportResult
from habit_tracker.services import export_import as export_import_service

router = APIRouter(tags=["export-import"])


@router.get("/export", response_model=ExportPayload)
async def export_habits(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Download all your habits, schedules, and check-in history as JSON
    — for backup, or to move to another instance via /import."""
    return await export_import_service.export_data(session, current_user)


@router.post("/import", response_model=ImportResult)
async def import_habits(
    body: ExportPayload,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Restore from a payload created by /export. Habits matched by name
    and entries matched by date are skipped rather than duplicated — see
    the returned counts for what was actually imported vs. skipped."""
    return await export_import_service.import_data(session, current_user, body)
