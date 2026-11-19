from pathlib import Path

import pytest

from workboard.config import Settings, load_settings


def test_load_settings_reads_env() -> None:
    env = {
        "WORKBOARD_SECRET": "s",
        "WORKBOARD_USERS_FILE": "/x/u.json",
        "WORKBOARD_DB": "/x/w.db",
    }
    assert load_settings(env) == Settings(Path("/x/u.json"), Path("/x/w.db"), "s")


def test_missing_secret_raises() -> None:
    with pytest.raises(RuntimeError):
        load_settings({})


def test_dev_mode_allows_missing_secret() -> None:
    assert load_settings({"WORKBOARD_DEV": "1"}).secret_key


def test_defaults() -> None:
    settings = load_settings({"WORKBOARD_SECRET": "s"})
    assert settings.users_file == Path("data/users.json")
    assert settings.db_path == Path("data/workboard.db")


def test_disable_password_defaults_off_and_reads_env() -> None:
    assert load_settings({"WORKBOARD_SECRET": "s"}).disable_password_check is False
    on = load_settings({"WORKBOARD_SECRET": "s", "WORKBOARD_DISABLE_PASSWORD": "1"})
    assert on.disable_password_check is True
    other = load_settings({"WORKBOARD_SECRET": "s", "WORKBOARD_DISABLE_PASSWORD": "true"})
    assert other.disable_password_check is False
