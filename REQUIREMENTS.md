# Habit Tracker — Requirements

Users create habits, check in daily, and see streaks. This spec covers
the API's scope, data model, and endpoint surface as decided through an
interview with the project owner. It supersedes the informal data-model
notes from the initial design discussion — the core streak/timezone
reasoning from that discussion is preserved below under Edge Cases.

## Scope decisions

| Area | Decision |
|---|---|
| Users | Single real user for now, but built multi-user-ready: every table carries `user_id`, real auth from day one (not a stub) |
| Client | A frontend is being built alongside this API — response shapes, CORS, and dedicated convenience endpoints matter |
| Deployment | Self-hosted via Docker + docker-compose, SQLite on a mounted volume |
| Database | SQLite |
| Auth mechanism | JWT bearer tokens, real register/login built now, access+refresh token flow |
| Password reset | Deferred (no email-based reset in v1) |
| Habit editing | Frequency changes are versioned — a `HabitSchedule` history, not a single mutable field, so past entries are judged by the schedule that was active when logged |
| Check-in edits | Any past entry is editable/deletable, no time limit; needs an `edited_at` audit field |
| Habit deletion | Soft delete (archive) — history is preserved, deletion is undoable |
| Quantifiable habits | Supported (e.g. "8 glasses of water") — but binary streak logic: full target must be met that day to count as done; `value` is stored for display only, no partial credit |
| Notifications | In scope with real delivery, **email only** — needs SMTP infra + a scheduler |
| "Today" view | Dedicated `/today` endpoint (all due-today habits + status in one call) rather than the frontend assembling it |
| CORS | Built in now, env-configurable allowed-origins list (deployment topology not finalized yet) |
| Stats | v1 returns current + longest streak only — no heatmap/analytics endpoints yet |
| Rate limiting | Basic protection on sensitive endpoints (login, check-in) |
| Export/Import | Both — JSON export and import (import needs a conflict policy, see below) |
| Token lifetime | Short-lived access token + refresh token flow (not one long-lived token) |

## Data model

**User**
- `id`, `email`, `hashed_password`
- `timezone` (IANA name), `day_start_hour` (default 0) — per-user
- `created_at`

**RefreshToken**
- `id`, `user_id`, `token_hash`, `expires_at`, `revoked_at` (nullable) — enables revocation/logout without storing raw tokens

**Habit**
- `id`, `user_id`, `name`, `description`
- `unit` (nullable, e.g. "glasses") and `target_value` (nullable numeric) — for quantifiable habits
- `created_at`, `archived_at` (nullable — soft delete)
- `current_streak`, `longest_streak` — denormalized cache; source of truth is always the Entry rows + schedule history, recomputed lazily and on write

**HabitSchedule** (versioned frequency — not a single mutable field on Habit)
- `id`, `habit_id`
- `frequency_type`: `daily` | `weekly_days` | `times_per_week`
- `frequency_config` (JSON: `{"days":[...]}` for weekly_days, or `{"target":N}` for times_per_week)
- `effective_from` (date)
- The schedule in force for a given `local_date` is the latest row with `effective_from <= local_date`. All scheduling/streak logic resolves against this table, never a static field.

**Entry** (one per habit per local calendar day)
- `id`, `habit_id`, `local_date`, `completed_at` (UTC), `status` (`done`/`skipped`), `value` (nullable)
- `edited_at` (nullable — set whenever a past entry is modified after initial creation)
- Unique constraint on `(habit_id, local_date)`

**NotificationPreference**
- `user_id`, `enabled` (bool), `remind_local_time`, `last_sent_local_date` (prevents duplicate sends per day)

## API surface (`/api/v1` prefix)

**Auth**
- `POST /auth/register`
- `POST /auth/login` — returns access + refresh token
- `POST /auth/refresh`
- `POST /auth/logout` — revokes the refresh token

**Habits**
- `POST /habits`
- `GET /habits` (`?include_archived=`)
- `GET /habits/{id}`
- `PATCH /habits/{id}` — name/description edits directly; a frequency change appends a new `HabitSchedule` row rather than mutating one in place
- `DELETE /habits/{id}` — soft delete
- `POST /habits/{id}/restore`

**Entries**
- `POST /habits/{id}/entries` — defaults to today's `local_date`, but accepts an explicit date for backfill
- `PATCH /habits/{id}/entries/{date}`
- `DELETE /habits/{id}/entries/{date}`
- `GET /habits/{id}/entries` — paginated, offset/limit

**Today & stats**
- `GET /today` — every non-archived habit scheduled today, with today's status
- `GET /habits/{id}/stats` — `current_streak`, `longest_streak`

**Settings**
- `GET /settings`
- `PATCH /settings` — timezone, day_start_hour, notification preferences

**Export/Import**
- `GET /export` — full JSON dump of the caller's habits, schedules, and entries
- `POST /import` — accepts that JSON shape

  **Open decision to confirm before building:** conflict policy when an
  imported habit/entry collides with existing data. Recommended default:
  *skip duplicates* (matched on habit name + entry `local_date`) and
  return a summary of what was skipped, rather than overwrite-by-default.

## Edge cases

**Timezones**
- Store `local_date` explicitly on each Entry, computed from
  `completed_at` + the user's timezone *at the moment of check-in* — never
  derive "today" from UTC on read. If a user's timezone setting changes
  later, past entries keep the local date they were logged under; only
  new entries use the new zone.
- DST transitions are a non-issue as long as streak logic always compares
  `date` values and never does "did 24 hours pass" math.

**Day boundary**
- Default midnight, configurable per user via `day_start_hour` — a 2am
  check-in can count as "yesterday" for users who want that.

**Missed days vs. a habit's own schedule**
- A day the habit wasn't scheduled on must never count as a miss —
  streak math always consults the active `HabitSchedule` row, not just
  "is there a gap in dates."
- For `times_per_week` habits, the streak unit is the **week**, evaluated
  only once the week is fully over (don't prematurely break a streak
  mid-week before the target could still be hit).

**Streak resets**
- A streak breaks the first time a *scheduled* unit (day or week) passes
  unsatisfied. This is a passive event — no user action triggers it — so
  streak is computed lazily on read by walking backward through Entry
  rows, never trusted from a cache alone.
- Archiving a habit **freezes** its streak rather than resetting it.
- Undoing a check-in invalidates/recomputes the cached streak.
- Backfilling a past day repairs a streak, since recomputation always
  reflects current Entry state (matches how apps like Loop Habit Tracker
  behave).
- Duplicate check-ins per day are prevented structurally by the
  `(habit_id, local_date)` unique constraint.

**Habit schedule changes**
- Editing a habit's frequency does not rewrite history: entries logged
  before the change are judged against the `HabitSchedule` row that was
  effective at the time, via `effective_from`.

**Quantifiable habits**
- A day counts as "done" only when `value >= target_value`; partial
  progress is stored and displayed but does not grant partial streak
  credit.

## Infrastructure choices

Filled in as sensible defaults during the interview, not separately
debated — worth flagging if any should be revisited before implementation
starts.

- **ORM**: SQLAlchemy 2.0 (async) + `aiosqlite` driver
- **Migrations**: Alembic
- **Password hashing**: `passlib` with argon2
- **JWT**: `PyJWT`
- **Config**: `pydantic-settings`, values from environment variables / `.env`
- **Notification scheduler**: APScheduler running in-process — avoids a
  separate broker (Celery+Redis) for a single self-hosted container
- **Email delivery**: user supplies their own SMTP credentials (host,
  port, user, pass) via env vars; no provider hardcoded
- **Rate limiting**: `slowapi`
- **Pagination**: offset/limit query params on list endpoints

## Not decided yet

- Import conflict policy (see Export/Import above) — recommendation given, not confirmed
- Test runner and style/lint rules (deferred by project owner; will be added to `CLAUDE.md` once chosen)
