from pydantic import BaseModel


class TodayItem(BaseModel):
    habit_id: int
    name: str
    status: str  # "done" | "skipped" | "pending"
    current_streak: int
