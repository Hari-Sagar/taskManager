# habit-tracker

A habit-tracking API: create habits, check in daily, see streaks. Built
with FastAPI, SQLAlchemy (async) + Alembic, and SQLite.

Streaks are maintained as a running counter on each habit, updated
transactionally on check-in, with a nightly reconciliation job to catch
breaks that happen passively (a day going by with no check-in). See
`ARCHITECTURE.md` for the full design and the reasoning behind that
choice.

## Docs

- [`REQUIREMENTS.md`](REQUIREMENTS.md) — product scope, decisions, data model, API surface, edge cases
- [`ARCHITECTURE.md`](ARCHITECTURE.md) — component layout, finalized data model, API contract, streak-calculation design
- [`PLAN.md`](PLAN.md) — the ordered, test-first build checklist (all 38 items complete)
- [`CLAUDE.md`](CLAUDE.md) — guidance for working in this repo (commands, layout, gotchas)

## Features

- Habits with flexible frequency: daily, specific weekdays, or N-times-per-week
- Quantifiable habits (e.g. "8 glasses of water") with a numeric target
- Current + longest streak per habit, with correct handling of backfills,
  edits, schedule changes, and archived habits
- JWT auth (access + refresh tokens, rotation on refresh)
- Email reminders for habits not yet checked in today
- JSON export/import for backup
- Rate limiting and CORS

## Quick start (local)

Requires Python 3.9+.

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/alembic upgrade head
.venv/bin/uvicorn habit_tracker.main:app --reload
```

The API is now at `http://localhost:8000` — interactive docs at
`http://localhost:8000/docs`.

## Quick start (Docker)

```bash
cp .env.example .env
# edit .env — set JWT_SECRET_KEY at minimum:
#   python3 -c "import secrets; print(secrets.token_urlsafe(32))"
docker compose up
```

SQLite data persists on a named volume across restarts/recreates.

## Running tests

```bash
.venv/bin/pytest
```

Run a single test:

```bash
.venv/bin/pytest tests/models/test_user.py::test_duplicate_email_raises_integrity_error
```

## Project layout

```
src/habit_tracker/
├── main.py           # FastAPI app, middleware
├── api/v1/            # route handlers only — no business logic
├── core/                # config, security, auth dependency, rate limiting
├── db/                    # SQLAlchemy base + async session
├── models/                 # ORM models
├── schemas/                  # Pydantic request/response models
├── services/                   # domain logic (streak engine, schedule
│                                  resolution, auth, entries, etc.) —
│                                  framework-agnostic, unit-tested directly
└── jobs/                          # nightly reconciliation + notification sweep
```
