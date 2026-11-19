# Team Work Board: MVP Design

Date: 2026-11-19 · Status: awaiting approval

## Intent

Teams track their work on one shared kanban board. After logging in, a person sees their team's board, creates work items, moves them between statuses, and assigns or reassigns them to teammates. They can also browse other teams' boards to see what those teams are working on. Source requirements: `docs/Notes.md` plus the decisions below.

## Goals

- Login against a local password file; no access to the board without it.
- Kanban UI with four columns: New, Planning, In progress, Finished.
- Work item fields: `title`, `description`, `assigned_to`, `status`.
- Multiple teams. Each user belongs to exactly one team.
- Any user can view any team's board. Writes (create, move, reassign, edit) are allowed only on the user's own team's items. All members of a team have the same permissions.
- SQLite stores the work items.
- The data model is shaped so a later move to Postgres and a real identity provider doesn't force a rewrite (target scale in the notes: 50k teams, 5M items, 500 concurrent users per team).

## Non-goals (MVP)

- Self-service signup, password reset, roles or per-item permissions.
- Cross-team writes or cross-team assignment (a possible later extension).
- Deleting items, comments, history/audit trail, notifications.
- Real-time push (WebSockets). The board polls instead.
- Meeting the full scale target. The MVP only avoids designing it out.

## Anti-goals

- A team boundary that leaks: a write to another team's item must be impossible, not merely hidden in the UI.
- Plaintext passwords anywhere, including the password file and logs.
- Tying the code so tightly to SQLite or to the password file that swapping either needs changes outside one module.

## Constraints

- Python 3.11+, uv, pytest, ruff, mypy; type hints on all signatures, Google-style docstrings (from the global `CLAUDE.md`).
- `.gitignore` excludes the real password file, the SQLite database and `.env`.

## Approaches considered (multi-team model)

| | Approach | Trade-off | Outcome |
|---|---|---|---|
| A | One DB, rows tagged with `team_id`, one team per user | Simplest; same schema works on Postgres; a person on two teams needs two accounts | **Chosen** |
| B | One DB, users in many teams via a memberships table | Handles multi-team people; adds team switcher and per-request membership checks | Rejected: user said one team per user |
| C | One SQLite file per team | Physical isolation; fails at 50k teams (files, migrations, no cross-team reads) | Rejected |

Cross-team permission: the user chose **read-only on other teams** over read plus cross-team assignment, and over full access everywhere.

## Design (my calls unless marked otherwise)

### Stack
FastAPI app serving a JSON API and one static single-page UI (vanilla JS, no build step, drag-and-drop between columns). Standard-library `sqlite3`. `bcrypt` for password hashing.

### Password file
`data/users.json` (gitignored; `users.example.json` committed). Entries: `username`, `password_hash` (bcrypt), `team`. Loaded at startup. A small CLI (`python -m workboard.users add <username> <team>`) prompts for a password and writes the hash, so nobody hand-edits hashes. Teams exist implicitly as the distinct `team` values in this file. Usernames are unique.

### Sessions
Server-side signing of a session cookie (Starlette `SessionMiddleware`), `HttpOnly`, `SameSite=Lax`. The signing secret comes from an environment variable, and the app refuses to start without it outside dev mode. The API accepts JSON only, which with `SameSite=Lax` is the CSRF protection for the MVP. Login failures return one generic message.

### Data model
Table `work_items`: `id` (integer PK), `team_id` (text, not null), `title` (text, not null, max 200 chars), `description` (text, default empty), `assigned_to` (text, nullable username), `status` (text, CHECK in the four values, default `New`), `created_by` (username), `created_at`, `updated_at`. Index on `(team_id, status)`. SQLite in WAL mode with a busy timeout. A small versioned schema-init step runs at startup.
`assigned_to` is nullable so an item can be created unassigned; the notes don't require one.

### Access rules (enforced server-side)
- Read: any authenticated user can read any team's items and member list.
- Write: allowed only when the item's `team_id` equals the caller's team, else 403. New items are always created in the caller's team (the client can't choose a team).
- `assigned_to` must be a member of the item's team, else 422.
- The write check lives in one function that every write endpoint calls.

### API
- `POST /api/login`, `POST /api/logout`, `GET /api/me`
- `GET /api/teams` (names, for the dropdown)
- `GET /api/teams/{team}/items`, `GET /api/teams/{team}/members`
- `POST /api/items` (create in own team)
- `PATCH /api/items/{id}` (any of status, assigned_to, title, description)

### UI
Login page, then the board. It opens on the user's home team with a team dropdown. Four columns, cards show title and assignee, click opens a detail panel with description and an assignee picker. A "New item" button. On another team's board the drag-and-drop and edit controls are disabled and a "read-only" banner shows. The board re-fetches every 10 seconds. Concurrent edits are last-write-wins for the MVP.

### Code layout
`src/workboard/` with separate modules: `auth` (password file and sessions), `repository` (all SQL; the only module that touches SQLite), `permissions` (the write check), `api` (routes), `static/` (UI). The auth and repository modules are the two swap points for Postgres and an identity provider later.

### Testing
pytest, run with `uv run pytest -v`. Cover: login success and failure, unauthenticated requests rejected, create and move and reassign on the home team, 403 on every write endpoint for another team's item, cross-team reads succeed, `assigned_to` must be a team member, status values validated. Tests use a temporary database and a temporary password file.

## Left to the builder

Exact file names, CSS and visual styling, the polling interval within reason, error message wording, and choice of test fixtures.

## My calls to check

1. Nullable `assigned_to`; items can be created unassigned.
2. Teams are defined only by the password file; there is no `teams` table.
3. No item deletion in the MVP.
4. 10-second polling and last-write-wins instead of WebSockets or conflict detection.
5. Vanilla JS with no frontend build step.
6. bcrypt, and a CLI for adding users.
