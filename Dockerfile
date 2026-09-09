# Runs on a real modern Python regardless of the host machine used to
# develop this — see CLAUDE.md's Environment note (dev is stuck on 3.9;
# the container isn't).
FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml alembic.ini ./
COPY alembic ./alembic
COPY src ./src

RUN pip install --no-cache-dir .

# The SQLite file lives on a mounted volume (docker-compose.yml) so it
# survives container restarts/recreates.
ENV HABIT_TRACKER_DATABASE_URL=sqlite+aiosqlite:////data/habit_tracker.db
VOLUME ["/data"]

EXPOSE 8000

# Apply migrations on every start, then serve — safe to run repeatedly,
# Alembic no-ops once the DB is already at head.
CMD ["sh", "-c", "alembic upgrade head && uvicorn habit_tracker.main:app --host 0.0.0.0 --port 8000"]
