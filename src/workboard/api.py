"""FastAPI application: JSON API for the work board."""

from __future__ import annotations

from dataclasses import asdict
from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException, Request
from pydantic import BaseModel, ConfigDict, StringConstraints, model_validator
from starlette.middleware.sessions import SessionMiddleware

from workboard.config import Settings
from workboard.permissions import ensure_can_write
from workboard.repository import STATUSES, Repository, WorkItem
from workboard.users import User, UserStore

Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


class LoginBody(BaseModel):
    """Login request."""

    model_config = ConfigDict(extra="forbid")
    username: str
    password: str


class ItemCreate(BaseModel):
    """Create-item request. The team is never client-supplied."""

    model_config = ConfigDict(extra="forbid")
    title: Title
    description: str = ""
    assigned_to: str | None = None


class ItemUpdate(BaseModel):
    """Partial update; at least one field is required."""

    model_config = ConfigDict(extra="forbid")
    title: Title | None = None
    description: str | None = None
    assigned_to: str | None = None
    status: str | None = None

    @model_validator(mode="after")
    def _check(self) -> ItemUpdate:
        if not self.model_fields_set:
            raise ValueError("at least one field is required")
        for name in ("title", "description", "status"):
            if name in self.model_fields_set and getattr(self, name) is None:
                raise ValueError(f"{name} cannot be null")
        if self.status is not None and self.status not in STATUSES:
            raise ValueError(f"status must be one of {list(STATUSES)}")
        return self


def _item_json(item: WorkItem) -> dict[str, Any]:
    return asdict(item)


def current_user(request: Request) -> User:
    """Resolve the logged-in user from the session or raise 401."""
    username = request.session.get("username")
    user = request.app.state.users.get(username) if isinstance(username, str) else None
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user  # type: ignore[no-any-return]


CurrentUser = Annotated[User, Depends(current_user)]


def create_app(settings: Settings) -> FastAPI:
    """Build the application.

    Args:
        settings: Runtime settings (password file, database, session secret).

    Returns:
        A configured FastAPI app with its database schema initialised.
    """
    users = UserStore(settings.users_file)
    repo = Repository(settings.db_path)
    repo.init_schema()

    app = FastAPI(title="Work Board")
    app.state.users = users
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.secret_key,
        session_cookie="workboard_session",
        same_site="lax",
        https_only=False,
    )

    def check_assignee(assigned_to: str | None, team: str) -> None:
        if assigned_to is not None and assigned_to not in users.members(team):
            raise HTTPException(status_code=422, detail=f"{assigned_to!r} is not on team {team!r}")

    @app.post("/api/login")
    def login(body: LoginBody, request: Request) -> dict[str, str]:
        user = users.authenticate(body.username, body.password)
        if user is None:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        request.session["username"] = user.username
        return {"username": user.username, "team": user.team}

    @app.post("/api/logout")
    def logout(request: Request) -> dict[str, bool]:
        request.session.clear()
        return {"ok": True}

    @app.get("/api/me")
    def me(user: CurrentUser) -> dict[str, str]:
        return {"username": user.username, "team": user.team}

    @app.post("/api/items", status_code=201)
    def create_item(body: ItemCreate, user: CurrentUser) -> dict[str, Any]:
        check_assignee(body.assigned_to, user.team)
        item = repo.create_item(
            user.team, body.title, body.description, body.assigned_to, user.username
        )
        return _item_json(item)

    @app.patch("/api/items/{item_id}")
    def update_item(item_id: int, body: ItemUpdate, user: CurrentUser) -> dict[str, Any]:
        item = repo.get_item(item_id)
        if item is None:
            raise HTTPException(status_code=404, detail="Item not found")
        ensure_can_write(user, item.team_id)
        changes = {name: getattr(body, name) for name in body.model_fields_set}
        check_assignee(changes.get("assigned_to"), item.team_id)
        updated = repo.update_item(item_id, **changes)
        if updated is None:
            raise HTTPException(status_code=404, detail="Item not found")
        return _item_json(updated)

    def known_team(team: str) -> str:
        if team not in users.teams():
            raise HTTPException(status_code=404, detail="Team not found")
        return team

    @app.get("/api/teams")
    def list_teams(user: CurrentUser) -> list[str]:
        return users.teams()

    @app.get("/api/teams/{team}/items")
    def list_items(team: str, user: CurrentUser) -> list[dict[str, Any]]:
        return [_item_json(i) for i in repo.list_items(known_team(team))]

    @app.get("/api/teams/{team}/members")
    def list_members(team: str, user: CurrentUser) -> list[str]:
        return users.members(known_team(team))

    return app
