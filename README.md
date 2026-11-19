# Work Board

Multi-team kanban board (MVP). Log in against a local password file, see your team's board,
create items, drag them between **New / Planning / In progress / Finished**, and assign them to
teammates. You can browse any team's board, but only write to your own team's items.

## Setup

```bash
uv sync
uv run python -m workboard.users add ann red      # prompts for a password; writes data/users.json
uv run python -m workboard.users add cy blue
```

`data/users.json` and the SQLite database are gitignored. `data/users.example.json` shows the format.

## Run

```bash
export WORKBOARD_SECRET="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
uv run uvicorn workboard.api:app_factory --factory --port 8000
```

Open http://localhost:8000. For local development only, `WORKBOARD_DEV=1` replaces the secret
with a random one per start (sessions reset on restart).

| Variable | Default | Purpose |
|---|---|---|
| `WORKBOARD_SECRET` | required (unless `WORKBOARD_DEV=1`) | signs session cookies |
| `WORKBOARD_USERS_FILE` | `data/users.json` | password file |
| `WORKBOARD_DB` | `data/workboard.db` | SQLite database |

## Develop

```bash
uv run pytest -v
uv run ruff format . && uv run ruff check . && uv run mypy .
```

## Scope and next steps

MVP limits: no signup or password reset, no item deletion, no cross-team writes, the board polls
every 10 s (no WebSockets), and concurrent edits are last-write-wins. Auth lives in
`workboard.users` and all SQL in `workboard.repository`, so a real identity provider or Postgres
can replace them without touching the API or UI.
