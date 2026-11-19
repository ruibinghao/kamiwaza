"""Application settings loaded from environment variables."""

from __future__ import annotations

import os
import secrets
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    """Runtime settings.

    Attributes:
        users_file: Path to the JSON password file.
        db_path: Path to the SQLite database.
        secret_key: Secret used to sign session cookies.
        disable_password_check: DEVELOPMENT ONLY. When true, login only needs an
            existing username and any password is accepted.
    """

    users_file: Path
    db_path: Path
    secret_key: str
    disable_password_check: bool = False


def load_settings(env: Mapping[str, str] | None = None) -> Settings:
    """Build settings from environment variables.

    Args:
        env: Mapping to read from; defaults to ``os.environ``.

    Returns:
        The resolved settings.

    Raises:
        RuntimeError: If no secret is configured and dev mode is off.
    """
    env = os.environ if env is None else env
    secret = env.get("WORKBOARD_SECRET", "")
    if not secret:
        if env.get("WORKBOARD_DEV") != "1":
            raise RuntimeError("WORKBOARD_SECRET must be set (or WORKBOARD_DEV=1 for development)")
        secret = secrets.token_hex(32)
    return Settings(
        users_file=Path(env.get("WORKBOARD_USERS_FILE", "data/users.json")),
        db_path=Path(env.get("WORKBOARD_DB", "data/workboard.db")),
        secret_key=secret,
        disable_password_check=env.get("WORKBOARD_DISABLE_PASSWORD") == "1",
    )
