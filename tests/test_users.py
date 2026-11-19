import json
from pathlib import Path

import pytest

from workboard.users import User, UserStore, add_user


@pytest.fixture
def path(tmp_path: Path) -> Path:
    return tmp_path / "users.json"


def test_add_user_stores_bcrypt_hash_not_plaintext(path: Path) -> None:
    add_user(path, "ann", "s3cret-pw", "red")
    text = path.read_text()
    assert "s3cret-pw" not in text
    assert json.loads(text)[0]["password_hash"].startswith("$2")


def test_authenticate_success_and_wrong_password(path: Path) -> None:
    add_user(path, "ann", "pw", "red")
    store = UserStore(path)
    assert store.authenticate("ann", "pw") == User("ann", "red")
    assert store.authenticate("ann", "nope") is None


def test_authenticate_unknown_user_returns_none(path: Path) -> None:
    add_user(path, "ann", "pw", "red")
    assert UserStore(path).authenticate("ghost", "pw") is None


def test_duplicate_username_raises_value_error(path: Path) -> None:
    add_user(path, "ann", "pw", "red")
    before = path.read_text()
    with pytest.raises(ValueError):
        add_user(path, "ann", "other", "blue")
    assert path.read_text() == before


def test_blank_fields_raise_value_error(path: Path) -> None:
    with pytest.raises(ValueError):
        add_user(path, " ", "pw", "red")
    with pytest.raises(ValueError):
        add_user(path, "ann", "", "red")
    with pytest.raises(ValueError):
        add_user(path, "ann", "pw", "")


def test_teams_and_members(path: Path) -> None:
    add_user(path, "bob", "pw", "red")
    add_user(path, "ann", "pw", "red")
    add_user(path, "cy", "pw", "blue")
    store = UserStore(path)
    assert store.teams() == ["blue", "red"]
    assert store.members("red") == ["ann", "bob"]
    assert store.members("nope") == []
    assert store.get("cy") == User("cy", "blue")
    assert store.get("ghost") is None


def test_missing_file_gives_empty_store(path: Path) -> None:
    store = UserStore(path)
    assert store.teams() == []
    assert store.authenticate("ann", "pw") is None


def test_malformed_json_raises_clear_error(path: Path) -> None:
    path.write_text("{not json")
    with pytest.raises(ValueError, match=str(path)):
        UserStore(path)


def test_empty_file_treated_as_malformed(path: Path) -> None:
    path.write_text("")
    with pytest.raises(ValueError, match=str(path)):
        UserStore(path)


def test_authenticate_without_password_check_accepts_any_password(path: Path) -> None:
    add_user(path, "ann", "pw", "red")
    store = UserStore(path)
    assert store.authenticate("ann", "wrong", verify_password=False) == User("ann", "red")
    assert store.authenticate("ann", "", verify_password=False) == User("ann", "red")
    assert store.authenticate("ghost", "pw", verify_password=False) is None
