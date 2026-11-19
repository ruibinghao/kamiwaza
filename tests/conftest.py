import json
from collections.abc import Callable
from pathlib import Path

import bcrypt
import pytest
from fastapi.testclient import TestClient

from workboard.api import create_app
from workboard.config import Settings

SEED = [("ann", "red"), ("bob", "red"), ("cy", "blue")]
_HASH = bcrypt.hashpw(b"pw", bcrypt.gensalt(rounds=4)).decode()  # cheap hash keeps tests fast


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    users_file = tmp_path / "users.json"
    entries = [{"username": n, "password_hash": _HASH, "team": t} for n, t in SEED]
    users_file.write_text(json.dumps(entries))
    return Settings(users_file, tmp_path / "w.db", "test-secret")


@pytest.fixture
def make_client(settings: Settings) -> Callable[[], TestClient]:
    app = create_app(settings)
    return lambda: TestClient(app)


@pytest.fixture
def client(make_client: Callable[[], TestClient]) -> TestClient:
    return make_client()


def login(client: TestClient, username: str, password: str = "pw") -> None:
    resp = client.post("/api/login", json={"username": username, "password": password})
    assert resp.status_code == 200, resp.text


@pytest.fixture
def ann(make_client: Callable[[], TestClient]) -> TestClient:
    c = make_client()
    login(c, "ann")
    return c


@pytest.fixture
def bob(make_client: Callable[[], TestClient]) -> TestClient:
    c = make_client()
    login(c, "bob")
    return c


@pytest.fixture
def cy(make_client: Callable[[], TestClient]) -> TestClient:
    c = make_client()
    login(c, "cy")
    return c
