from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tests.conftest import login
from workboard.config import Settings


def test_login_success_sets_cookie_and_me_returns_identity(client: TestClient) -> None:
    resp = client.post("/api/login", json={"username": "ann", "password": "pw"})
    assert resp.status_code == 200
    assert resp.json() == {"username": "ann", "team": "red"}
    assert client.get("/api/me").json() == {"username": "ann", "team": "red"}


def test_wrong_password_and_unknown_user_get_identical_401(client: TestClient) -> None:
    bad_pw = client.post("/api/login", json={"username": "ann", "password": "x"})
    unknown = client.post("/api/login", json={"username": "ghost", "password": "x"})
    assert bad_pw.status_code == unknown.status_code == 401
    assert bad_pw.json() == unknown.json() == {"detail": "Invalid credentials"}


def test_me_without_login_is_401(client: TestClient) -> None:
    assert client.get("/api/me").status_code == 401


def test_logout_clears_session(client: TestClient) -> None:
    login(client, "ann")
    assert client.post("/api/logout").status_code == 200
    assert client.get("/api/me").status_code == 401


def test_session_cookie_is_httponly_and_samesite_lax(client: TestClient) -> None:
    resp = client.post("/api/login", json={"username": "ann", "password": "pw"})
    cookie = resp.headers["set-cookie"].lower()
    assert "httponly" in cookie
    assert "samesite=lax" in cookie


def test_app_refuses_to_start_without_any_users(tmp_path: Path) -> None:
    from workboard.api import create_app
    from workboard.config import Settings

    missing = tmp_path / "nope.json"
    with pytest.raises(RuntimeError, match=str(missing)):
        create_app(Settings(missing, tmp_path / "w.db", "s"))
    empty = tmp_path / "empty.json"
    empty.write_text("[]")
    with pytest.raises(RuntimeError, match=str(empty)):
        create_app(Settings(empty, tmp_path / "w.db", "s"))


def test_password_check_can_be_disabled_but_username_must_exist(
    settings: Settings, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    from dataclasses import replace

    from fastapi.testclient import TestClient

    from workboard.api import create_app

    with caplog.at_level("WARNING"):
        app = create_app(replace(settings, disable_password_check=True))
    assert "password" in caplog.text.lower()
    c = TestClient(app)
    ok = c.post("/api/login", json={"username": "ann", "password": "totally-wrong"})
    assert ok.status_code == 200 and ok.json() == {"username": "ann", "team": "red"}
    assert c.get("/api/me").status_code == 200
    unknown = TestClient(app).post("/api/login", json={"username": "ghost", "password": "x"})
    assert unknown.status_code == 401


def test_password_check_is_enforced_by_default(client: TestClient) -> None:
    resp = client.post("/api/login", json={"username": "ann", "password": "totally-wrong"})
    assert resp.status_code == 401
