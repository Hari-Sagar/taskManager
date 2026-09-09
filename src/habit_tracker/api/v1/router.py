from fastapi import APIRouter

from habit_tracker.api.v1 import auth, entries, export_import, habits, settings, today

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(habits.router)
api_router.include_router(entries.router)
api_router.include_router(today.router)
api_router.include_router(settings.router)
api_router.include_router(export_import.router)
