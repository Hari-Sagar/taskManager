# Habit Tracker — Architecture

This document covers component layout, the full data model, the API
contract per endpoint, and the reasoning behind the streak-calculation
design. It builds on `REQUIREMENTS.md` (scope and decisions) and
resolves the two open questions from that spec — data model and streak
calculation — that were deliberately left as choices to make explicitly.

**Decision made:** denormalized running counters on `Habit`
(`current_streak`/`longest_streak`), updated transactionally on check-in.
Read-time computation was considered and rejected — see below.

## Component layout

```
src/habit_tracker/
├── main.py                 # FastAPI app factory: mounts routers, CORS, rate limiting
├── core/
│   ├── config.py            # pydantic-settings (env vars: DB path, JWT secret, SMTP, CORS origins)
│   ├── security.py          # password hashing (argon2), JWT encode/decode
│   └── deps.py               # FastAPI dependencies: get_db, get_current_user
├── db/
│   ├── session.py            # async engine/session factory (SQLAlchemy 2.0 + aiosqlite)
│   └── base.py                # declarative base, shared mixins (id, created_at)
├── models/                    # SQLAlchemy ORM — one module per table
│   ├── user.py, refresh_token.py, habit.py, habit_schedule.py
│   └── entry.py, notification_preference.py
├── schemas/                    # Pydantic request/response models, mirrors models/
├── api/v1/
│   ├── router.py               # aggregates sub-routers under /api/v1
│   └── auth.py, habits.py, entries.py, today.py, settings.py, export_import.py
├── services/                    # domain logic — framework-agnostic, unit-testable without FastAPI
│   ├── streak.py                 # apply_checkin() fast path + recompute() fallback — see below
│   ├── schedule.py                 # resolves active HabitSchedule for a date; "is due" / period-key logic
│   ├── auth.py                      # register/login/refresh business logic
│   └── notifications.py              # daily job: who hasn't checked in, sends email
├── jobs/
│   └── scheduler.py                 # APScheduler setup: nightly reconciliation + notification sweep
└── alembic/                          # migrations
```

Layering: `api/` handles HTTP concerns only (parsing, status codes, auth
dependency) and delegates to `services/`; `services/` contains the actual
domain rules (streak math, schedule resolution) and is what unit tests
target directly; `models/` is persistence only, no business logic. This
keeps the streak algorithm testable without spinning up FastAPI.

## Data model

**User** — `id` (PK), `email` (unique), `hashed_password`, `timezone`, `day_start_hour` (default 0), `created_at`

**RefreshToken** — `id`, `user_id` (FK), `token_hash`, `expires_at`, `revoked_at` (nullable), `created_at`

**Habit** — `id`, `user_id` (FK), `name`, `description` (nullable), `unit` (nullable), `target_value` (nullable numeric), `created_at`, `archived_at` (nullable)
- `current_streak` (int, default 0)
- `longest_streak` (int, default 0)
- `streak_last_counted_period_start` (date, nullable) — the start of the most recent *period* already reflected in `current_streak`. For `daily`/`weekly_days` habits a period is a single day (so this is just a `local_date`); for `times_per_week` habits a period is a week (this holds that week's Monday). Generalizing to "period start" lets one column drive the fast-path check for every frequency type. This field is new relative to `REQUIREMENTS.md`'s original sketch — it's what makes the O(1) increment path possible (see Streak design below).

**HabitSchedule** — `id`, `habit_id` (FK), `frequency_type` (`daily`|`weekly_days`|`times_per_week`), `frequency_config` (JSON), `effective_from` (date). Active schedule for a `local_date` = latest row with `effective_from <= local_date`.

**Entry** — `id`, `habit_id` (FK), `local_date`, `completed_at` (UTC datetime), `status` (`done`|`skipped`), `value` (nullable numeric), `edited_at` (nullable), `created_at`. Unique on `(habit_id, local_date)`.

**NotificationPreference** — `user_id` (PK/FK), `enabled` (bool), `remind_local_time`, `last_sent_local_date` (nullable)

## Streak design — the running counter

`services/streak.py` exposes two entry points; every write path calls one
of them, never touches `current_streak`/`longest_streak` directly:

**`apply_checkin(habit, entry)`** — called from `POST /habits/{id}/entries` when a new entry is created with `status=done` (and, for quantifiable habits, `value >= target_value`):
1. Resolve the entry's *period* (its `local_date`, or the ISO week start if the active schedule is `times_per_week`).
2. Compute `expected_next_period` = the period immediately following `streak_last_counted_period_start`, per the active `HabitSchedule`.
3. **Fast path** — if this entry's period `== expected_next_period` (i.e. it's the very next scheduled unit in sequence, no gap, no backfill): `current_streak += 1`, `longest_streak = max(longest_streak, current_streak)`, `streak_last_counted_period_start = period`. One UPDATE, O(1).
4. **Fallback** — anything else (first-ever entry, a gap since the last counted period, or a backfilled date that isn't the immediate next one) calls `recompute(habit)` instead.

**`recompute(habit)`** — walks this habit's `Entry` rows against its `HabitSchedule` history from scratch (bounded to one habit, not the whole table) and overwrites `current_streak`, `longest_streak`, `streak_last_counted_period_start` directly. This is the single source of truth for "what should the counters be" — the fast path is purely an optimization that must agree with it, never a separate algorithm.

Called from:
- `apply_checkin`'s fallback branch (above)
- `PATCH /habits/{id}/entries/{date}` and `DELETE /habits/{id}/entries/{date}` — always, unconditionally: edits/deletes touch past state, so correctness wins over the O(1) shortcut here
- `PATCH /habits/{id}` when it appends a new `HabitSchedule` row (the schedule change can retroactively affect what "expected next period" means)
- The nightly reconciliation job (below), for any habit whose expected next period has fully elapsed with no `done` entry — this is what catches **passive** breaks, which no write ever triggers

**Transaction boundary**: the `Entry` insert/update/delete and the `Habit` counter update happen in one DB transaction. If the process dies between them, both roll back together — the counters can never point to a world where the entry write did or didn't happen but the other didn't match. SQLite serializes writes per-connection already; wrapping both statements in one `async with session.begin():` block is sufficient, no extra locking needed at this scale.

**Nightly job** (`jobs/scheduler.py`, APScheduler, in-process): for every non-archived habit, if its expected next period (per `streak_last_counted_period_start` + active schedule) has fully elapsed without a qualifying entry, call `recompute(habit)`. Runs once daily, right after each user's configured `day_start_hour` would have rolled over for their timezone (or a single fixed late-night UTC pass, since checking is cheap — exact scheduling is an implementation detail, not an architectural one). This job already has to exist for email notifications (`REQUIREMENTS.md`), so it's shared infrastructure, not new cost incurred by this streak design.

## Why read-time computation was rejected

An earlier comparison weighed read-time computation (compute the streak
from `Entry` rows on every read, cache nothing) against maintaining a
counter. The case *for* read-time computation was "no write-path
complexity, cost is cheap at personal-tracker scale." That held up for a
single read. It stops holding up once you look at where streak values
actually get read:

1. **`GET /today` is the app's home screen** — it computes/returns a
   status for every non-archived habit in one call, and is the single
   most frequently hit endpoint in the whole system (loaded on every app
   open, every check-in refresh). Read-time computation means that
   endpoint pays a full history walk *per habit* on *every single load*,
   not once. A running counter turns that into N cheap column reads.

2. **The check-in response needs the new streak immediately anyway.**
   When a user checks off a habit, the frontend wants to show "streak: 12"
   right in that response, optimistically and correctly. Under read-time
   computation, the server still has to compute the streak once, at write
   time, to return it — the "no write-path cost" argument was never fully
   true for this endpoint specifically. Persisting that value once
   computed is strictly less total work than computing it at write time
   *and then recomputing it* on the next `/today` load, `/stats` call, or
   notification check.

3. **The notification job needs completion state for every habit, every
   user, every day** — another full sweep under read-time computation.
   With the counter design this job degrades to checking one date field
   per habit instead of walking history.

4. **"Cheap at today's scale" is a scaling assumption, not a guarantee.**
   The already-planned Import feature (`REQUIREMENTS.md`) lets a user
   load years of historical entries in one shot; multi-year personal
   usage compounds the same way. A counter design means query cost never
   grows with history length at all — the O(1) property holds regardless
   of how much data accumulates, rather than staying fast only as long as
   nobody imports or accumulates much history.

5. **The strongest argument *for* read-time computation — that edits and
   backfills break clean incrementality — is real, but it's an argument
   against *pure* incrementality, not against maintaining a counter at
   all.** The fast-path/fallback split above keeps the O(1) property for
   the common case (checking in for the next expected day, which is the
   overwhelming majority of writes in normal use) while routing the rare
   cases (backfill, edit, undo, schedule change) through the same bounded
   recompute that read-time computation would have used for *every* read.
   Net effect: correctness-critical paths get read-time computation's
   approach exactly where it matters, and the hot path gets O(1) —
   without carrying full history-walk cost on every request.

6. **The nightly reconciliation job is required either way** — passive
   breaks (a day elapsing with no check-in) don't trigger *any* write
   under either design, so read-time computation doesn't actually
   eliminate the need for a background sweep; it only shifts where
   staleness gets caught (on the next read, vs. proactively overnight).
   That's not a point in read-time computation's favor once notifications
   already require the same job to exist.

## API contract (`/api/v1` prefix, JWT bearer auth except register/login)

**Auth**
- `POST /auth/register` — `{email, password}` → `201 {id, email, created_at}`; `409` if email taken
- `POST /auth/login` — `{email, password}` → `200 {access_token, refresh_token, token_type: "bearer"}`; `401` on bad credentials
- `POST /auth/refresh` — `{refresh_token}` → `200 {access_token, refresh_token}` (refresh token rotates); `401` if invalid/revoked/expired
- `POST /auth/logout` — `{refresh_token}` → `204`; revokes it

**Habits**
- `POST /habits` — `{name, description?, unit?, target_value?, frequency_type, frequency_config}` → `201` Habit (incl. `current_streak: 0, longest_streak: 0`)
- `GET /habits?include_archived=false` → `200 [Habit...]`
- `GET /habits/{id}` → `200` Habit (incl. active schedule, streak fields); `404`
- `PATCH /habits/{id}` — `{name?, description?, unit?, target_value?, frequency_type?, frequency_config?}` → `200` updated Habit; a frequency change appends a new `HabitSchedule` row (`effective_from` = today's `local_date`) and triggers `recompute()`, it never mutates a schedule row in place
- `DELETE /habits/{id}` → `204`; sets `archived_at` (streak counters freeze — the nightly job skips archived habits)
- `POST /habits/{id}/restore` → `200` Habit; clears `archived_at`

**Entries**
- `POST /habits/{id}/entries` — `{local_date? (default today), status, value?}` → `201` Entry; runs `apply_checkin()`; `409` if `(habit_id, local_date)` already exists (use `PATCH` to change it)
- `PATCH /habits/{id}/entries/{date}` — `{status?, value?}` → `200` Entry (sets `edited_at`); runs `recompute()` unconditionally
- `DELETE /habits/{id}/entries/{date}` → `204`; runs `recompute()` unconditionally
- `GET /habits/{id}/entries?limit=&offset=` → `200 {items: [Entry...], total}`

**Today & stats**
- `GET /today` → `200 [{habit_id, name, status: done|skipped|pending, current_streak}]` for every non-archived habit scheduled today — reads `current_streak` directly off `Habit`, no computation
- `GET /habits/{id}/stats` → `200 {current_streak, longest_streak}`

**Settings**
- `GET /settings` → `200 {timezone, day_start_hour, notifications: {enabled, remind_local_time}}`
- `PATCH /settings` — partial body → `200` updated Settings

**Export/Import**
- `GET /export` → `200 {habits: [...], schedules: [...], entries: [...]}` (streak counters excluded — they're derived state, re-established by `recompute()` on import, not exported/imported as raw values)
- `POST /import` — same shape → `200 {imported: {habits, entries}, skipped: {habits, entries}}`; skip-duplicates policy per `REQUIREMENTS.md`; each imported habit gets `recompute()` run once at the end rather than replaying `apply_checkin()` per historical entry

## Next steps

Implementation (models, `services/streak.py`, Alembic migration,
endpoints) is separate future work. When it happens, `services/streak.py`
should get unit tests covering: the fast-path increment, the fallback on
a backfilled date, the fallback on edit/delete, a `times_per_week`
habit's week-boundary handling, and the nightly job catching a passive
break — all without needing FastAPI or a real HTTP request, per the
layering above.
