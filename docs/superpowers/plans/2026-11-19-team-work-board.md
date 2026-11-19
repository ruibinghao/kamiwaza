# Team Work Board Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A multi-team kanban work board: password-file login, SQLite-backed work items, read-everywhere / write-own-team access.

**Architecture:** FastAPI app with a JSON API and a static vanilla-JS UI. Four focused modules: `config`, `users` (password file + CLI), `repository` (all SQL), `permissions` (single write check), wired together in `api`. Auth and repository are the swap points for an identity provider and Postgres later.

**Tech Stack:** Python 3.11+, uv, FastAPI, uvicorn, itsdangerous (via Starlette sessions), bcrypt, stdlib sqlite3, pytest, httpx (TestClient), ruff, mypy.

**Spec:** `docs/superpowers/specs/2026-11-19-team-work-board-design.md`

## Global Constraints

- Python 3.11+; type hints on every signature; Google-style docstrings on public modules, classes, methods.
- Commands: `uv run pytest -v`, `uv run ruff format .`, `uv run ruff check .`, `uv run mypy .`
- Statuses exactly: `New`, `Planning`, `In progress`, `Finished` (default `New`).
- Work item fields: `title` (required, max 200 chars), `description` (default empty), `assigned_to` (nullable username), `status`.
- Password file `data/users.json` entries: `username`, `password_hash` (bcrypt), `team`. Never plaintext. Real file, DB and `.env` are gitignored; `users.example.json` committed.
- Session cookie: `HttpOnly`, `SameSite=Lax`, secret from env `WORKBOARD_SECRET` (app refuses to start without it unless `WORKBOARD_DEV=1`). JSON-only API.
- Read: any authenticated user, any team. Write: only when item's team equals caller's team, else 403. `assigned_to` must belong to the item's team, else 422. New items always created in the caller's team.
- SQLite in WAL mode with busy timeout. No item deletion, no WebSockets (UI polls every 10 s), last-write-wins.
- Login failure returns one generic message.

## Review Focus

1. Item text containing HTML or script (`<script>`, `<img onerror>`): the UI must render it as text. Pinned in Task 6.
2. Blank or whitespace-only title, title over 200 chars: rejected with 422, not stored. Pinned in Task 4.
3. `PATCH` with an empty body, an unknown status, or an unknown field: 422, nothing changed. Pinned in Task 4.
4. Unknown team in the URL or a nonexistent item id: 404, not a 500 or an empty 200. Pinned in Tasks 4 and 5.
5. Missing, empty or malformed `users.json`; duplicate username in the CLI: a clear error, not a crash or silent overwrite. Pinned in Task 2.

---

### Task 1: Project scaffold and settings

**Files:**
- Create: `pyproject.toml`, `.gitignore`, `data/users.example.json`, `src/workboard/__init__.py`, `src/workboard/config.py`, `tests/__init__.py`, `tests/test_config.py`

**Interfaces:**
- Produces: `Settings` (frozen dataclass: `users_file: Path`, `db_path: Path`, `secret_key: str`) and `load_settings(env: Mapping[str, str] | None = None) -> Settings` in `workboard.config`.

- [ ] **Step 1:** Run `git init`; `uv init --package` equivalent: write `pyproject.toml` (name `workboard`, src layout, `requires-python >=3.11`, deps fastapi, uvicorn, bcrypt, itsdangerous, httpx; dev deps pytest, ruff, mypy). Write `.gitignore` (Python defaults plus `.venv/`, `data/users.json`, `data/*.db*`, `.env`). Run `uv sync`.
- [ ] **Step 2: Failing tests** in `tests/test_config.py`:
  - `test_load_settings_reads_env`: env `WORKBOARD_SECRET="s"`, `WORKBOARD_USERS_FILE="/x/u.json"`, `WORKBOARD_DB="/x/w.db"` gives `Settings(Path("/x/u.json"), Path("/x/w.db"), "s")`.
  - `test_missing_secret_raises`: no secret, no dev flag raises `RuntimeError`.
  - `test_dev_mode_allows_missing_secret`: `WORKBOARD_DEV="1"` returns a non-empty secret.
  - `test_defaults`: only `WORKBOARD_SECRET` set gives `data/users.json` and `data/workboard.db`.
- [ ] **Step 3:** Run `uv run pytest tests/test_config.py -v`; expect FAIL (module missing).
- [ ] **Step 4:** Implement `config.py` per the interface. Write `data/users.example.json` with two sample entries on two teams (hashes are placeholders and documented as such).
- [ ] **Step 5:** Run tests, `uv run ruff check .`, `uv run mypy .`; expect PASS.
- [ ] **Step 6:** `git add -A && git commit -m "chore: scaffold project and settings"` (with the attribution line from the session).

### Task 2: Password file and user CLI

**Files:**
- Create: `src/workboard/users.py`, `tests/test_users.py`

**Interfaces:**
- Produces in `workboard.users`:
  - `User` (frozen dataclass: `username: str`, `team: str`)
  - `class UserStore`: `__init__(self, path: Path)`; `authenticate(self, username: str, password: str) -> User | None`; `get(self, username: str) -> User | None`; `teams(self) -> list[str]` (sorted, distinct); `members(self, team: str) -> list[str]` (sorted).
  - `add_user(path: Path, username: str, password: str, team: str) -> None` (raises `ValueError` on duplicate username or blank fields; creates the file if absent).
  - `main(argv: list[str] | None = None) -> int` (CLI: `add <username> <team>`, password via `getpass`).

- [ ] **Step 1: Failing tests** (use `tmp_path`):
  - `test_add_user_stores_bcrypt_hash_not_plaintext`: file text does not contain the password; `password_hash` starts with `$2`.
  - `test_authenticate_success_and_wrong_password` (returns `User("ann","red")` / `None`).
  - `test_authenticate_unknown_user_returns_none`.
  - `test_duplicate_username_raises_value_error` and file unchanged.
  - `test_teams_and_members`: users on teams red and blue give `teams() == ["blue","red"]`, members sorted.
  - `test_missing_file_gives_empty_store`; `test_malformed_json_raises_clear_error` (`ValueError` mentioning the path); `test_empty_file_treated_as_malformed`.
- [ ] **Step 2:** Run `uv run pytest tests/test_users.py -v`; expect FAIL.
- [ ] **Step 3:** Implement. Load the file once in `__init__`; verify with `bcrypt.checkpw`; for an unknown user still run a dummy `checkpw` so timing doesn't reveal which usernames exist. `add_user` writes atomically (temp file then `os.replace`).
- [ ] **Step 4:** Run tests; expect PASS. Run ruff and mypy.
- [ ] **Step 5:** Commit `feat: password file store and user CLI`.

### Task 3: Repository (SQLite)

**Files:**
- Create: `src/workboard/repository.py`, `tests/test_repository.py`

**Interfaces:**
- Produces in `workboard.repository`:
  - `STATUSES: tuple[str, ...] = ("New", "Planning", "In progress", "Finished")`
  - `WorkItem` (frozen dataclass: `id: int`, `team_id: str`, `title: str`, `description: str`, `assigned_to: str | None`, `status: str`, `created_by: str`, `created_at: str`, `updated_at: str`; timestamps ISO-8601 UTC)
  - `class Repository`: `__init__(self, db_path: Path)`; `init_schema(self) -> None` (idempotent, WAL, busy timeout, `PRAGMA user_version`); `create_item(self, team_id: str, title: str, description: str, assigned_to: str | None, created_by: str) -> WorkItem`; `get_item(self, item_id: int) -> WorkItem | None`; `list_items(self, team_id: str) -> list[WorkItem]` (ordered by id); `update_item(self, item_id: int, **fields: str | None) -> WorkItem | None` (allowed keys: `title`, `description`, `assigned_to`, `status`; bumps `updated_at`; unknown key raises `ValueError`).

- [ ] **Step 1: Failing tests** (temp DB per test):
  - `test_create_defaults_status_new_and_returns_item`.
  - `test_list_items_only_returns_requested_team`.
  - `test_update_changes_fields_and_bumps_updated_at`.
  - `test_update_unknown_id_returns_none`; `test_update_unknown_field_raises`.
  - `test_invalid_status_rejected_by_db` (`update_item(id, status="Done")` raises).
  - `test_init_schema_is_idempotent`; `test_journal_mode_is_wal`.
  - `test_assigned_to_can_be_set_to_none`.
  - `test_sql_injection_in_title_is_stored_literally` (title `x'); DROP TABLE work_items;--` round-trips).
- [ ] **Step 2:** Run; expect FAIL.
- [ ] **Step 3:** Implement with parameterized queries only, one short-lived connection per call (`sqlite3.connect(..., timeout=5)`), `CHECK(status IN (...))` and index on `(team_id, status)` in the schema.
- [ ] **Step 4:** Run tests, ruff, mypy; expect PASS.
- [ ] **Step 5:** Commit `feat: sqlite repository for work items`.

### Task 4: App, auth routes, permissions, and item writes

**Files:**
- Create: `src/workboard/permissions.py`, `src/workboard/api.py`, `tests/conftest.py`, `tests/test_auth_api.py`, `tests/test_items_write_api.py`

**Interfaces:**
- Consumes: `Settings`, `UserStore`, `User`, `Repository`, `STATUSES`, `WorkItem`.
- Produces:
  - `workboard.permissions.ensure_can_write(user: User, item_team: str) -> None` raises `HTTPException(403)` when `user.team != item_team`.
  - `workboard.api.create_app(settings: Settings) -> FastAPI` with routes `POST /api/login` (`{username,password}` → 200 `{username,team}`; failure 401 `{"detail":"Invalid credentials"}`), `POST /api/logout`, `GET /api/me`, `POST /api/items` (`{title, description?, assigned_to?}` → 201 item JSON), `PATCH /api/items/{id}` (any of `status, assigned_to, title, description` → 200 item JSON).
  - A dependency `current_user(request) -> User` returning 401 when no session.
  - `tests/conftest.py` fixtures: `settings`, `client` (TestClient), `login(client, username)` helper, seeded users `ann`, `bob` on team `red`, `cy` on team `blue` (password `pw`).
  - Item JSON shape: all `WorkItem` fields.

- [ ] **Step 1: Failing tests, auth** (`test_auth_api.py`): login success sets cookie and `/api/me` returns `{"username":"ann","team":"red"}`; wrong password and unknown user both 401 with identical body; `/api/me` without login 401; logout then `/api/me` 401; cookie has `HttpOnly` and `SameSite=lax`.
- [ ] **Step 2: Failing tests, writes** (`test_items_write_api.py`, logged in as `ann`):
  - create returns 201, `team_id == "red"`, `status == "New"`, `created_by == "ann"`.
  - create ignores a client-supplied `team_id`.
  - blank, whitespace-only, and 201-character titles give 422.
  - `assigned_to="cy"` (other team) gives 422; `assigned_to="bob"` gives 201.
  - PATCH status to each valid value succeeds; `"Done"` gives 422.
  - PATCH reassign to `bob`, then to `null` (unassign) works; reassign to `cy` gives 422.
  - PATCH empty body gives 422; unknown field gives 422; nonexistent id gives 404.
  - Any teammate (`bob`) can PATCH `ann`'s item.
  - `cy` (team blue) PATCH on a red item gives 403 and the item is unchanged; unauthenticated POST/PATCH give 401.
- [ ] **Step 3:** Run both files; expect FAIL.
- [ ] **Step 4:** Implement. Use Pydantic models with `extra="forbid"`, `title` stripped and constrained 1 to 200 chars. Install `SessionMiddleware` with `same_site="lax"`, `https_only=False` in dev, secret from settings. Every write endpoint loads the item, then calls `ensure_can_write` before touching the repository.
- [ ] **Step 5:** Run tests, ruff, mypy; expect PASS.
- [ ] **Step 6:** Commit `feat: auth, permissions and item write endpoints`.

### Task 5: Cross-team read endpoints

**Files:**
- Modify: `src/workboard/api.py`
- Test: `tests/test_items_read_api.py`

**Interfaces:**
- Consumes: everything from Task 4.
- Produces: `GET /api/teams` → `["blue","red"]`; `GET /api/teams/{team}/items` → list of item JSON; `GET /api/teams/{team}/members` → list of usernames. Unknown team gives 404; unauthenticated gives 401.

- [ ] **Step 1: Failing tests:** `ann` sees red items; `ann` can read blue items and members (cross-team read allowed); items from one team never appear in another's list; `/api/teams` lists distinct teams; unknown team 404 on both endpoints; unauthenticated 401; read endpoints never modify data.
- [ ] **Step 2:** Run; expect FAIL.
- [ ] **Step 3:** Implement the three routes using `UserStore.teams()/members()` and `Repository.list_items`.
- [ ] **Step 4:** Run the full suite (`uv run pytest -v`), ruff, mypy; expect PASS.
- [ ] **Step 5:** Commit `feat: cross-team read endpoints`.

### Task 6: Kanban UI

**Files:**
- Create: `src/workboard/static/index.html`, `src/workboard/static/app.js`, `src/workboard/static/app.css`, `tests/test_static.py`
- Modify: `src/workboard/api.py` (serve `/` and `/static`)

**Interfaces:**
- Consumes: all `/api/*` routes from Tasks 4 and 5.

- [ ] **Step 1: Failing tests** (`test_static.py`): `GET /` returns 200 HTML containing a login form; `GET /static/app.js` returns 200; `app.js` source contains no `innerHTML` assignment (guards Review Focus 1 by construction, all dynamic text goes through `textContent`).
- [ ] **Step 2:** Run; expect FAIL.
- [ ] **Step 3:** Implement the UI. Login view, then board view: four columns from the status list, cards with title and assignee, detail panel (description, assignee `<select>` from `/members`), "New item" form, team dropdown defaulting to the home team, 10-second polling of the items endpoint, drag-and-drop calling `PATCH` with the new status. When the viewed team differs from the home team: show a "read-only" banner and disable drag, edit and create controls. On a 401 response, return to the login view. All user-supplied text is set via `textContent`.
- [ ] **Step 4:** Run tests; expect PASS. Then run the server (`WORKBOARD_DEV=1 uv run uvicorn workboard.api:app_factory --factory`; add `app_factory() -> FastAPI` here in Task 6 if not yet present, Task 7 only documents it) with two seeded users and check in a browser: login, create, drag between columns, reassign, switch to another team (controls disabled), item titled `<img src=x onerror=alert(1)>` shows as literal text.
- [ ] **Step 5:** Commit `feat: kanban UI`.

### Task 7: Run docs and final verification

**Files:**
- Create: `README.md`
- Modify: `src/workboard/api.py` (confirm `app_factory() -> FastAPI`, which reads `load_settings()` and is used by uvicorn `--factory`, exists from Task 6)

- [ ] **Step 1:** Write README: setup (`uv sync`), adding users (`uv run python -m workboard.users add ann red`), required env vars, run command, test command, scope notes (non-goals, how to swap auth and repository later).
- [ ] **Step 2:** Run `uv run ruff format .`, `uv run ruff check .`, `uv run mypy .`, `uv run pytest -v`; all clean and passing.
- [ ] **Step 3:** Start the server from a clean checkout following only the README; confirm the board loads and a login works.
- [ ] **Step 4:** Commit `docs: README and run entrypoint`.
