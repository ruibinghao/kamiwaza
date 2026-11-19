from pathlib import Path

from fastapi.testclient import TestClient

STATIC = Path(__file__).parent.parent / "src" / "workboard" / "static"


def test_root_serves_html_with_login_form(client: TestClient) -> None:
    resp = client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert 'id="login-form"' in resp.text


def test_static_js_and_css_served(client: TestClient) -> None:
    assert client.get("/static/app.js").status_code == 200
    assert client.get("/static/app.css").status_code == 200


def test_app_js_never_uses_innerhtml_so_user_text_stays_text() -> None:
    source = (STATIC / "app.js").read_text()
    for banned in ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write"):
        assert banned not in source


def test_app_factory_builds_app_from_env(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from workboard.api import app_factory
    from workboard.users import add_user

    add_user(tmp_path / "u.json", "ann", "pw", "red")

    monkeypatch.setenv("WORKBOARD_DEV", "1")
    monkeypatch.setenv("WORKBOARD_USERS_FILE", str(tmp_path / "u.json"))
    monkeypatch.setenv("WORKBOARD_DB", str(tmp_path / "w.db"))
    assert TestClient(app_factory()).get("/").status_code == 200


def test_board_has_visible_error_area_used_for_failed_moves(client: TestClient) -> None:
    assert 'id="board-error"' in client.get("/").text
    assert "board-error" in (STATIC / "app.js").read_text()
