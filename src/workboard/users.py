"""Password-file user store and the ``add`` CLI."""

from __future__ import annotations

import argparse
import getpass
import json
import os
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

import bcrypt

_DUMMY_HASH = bcrypt.hashpw(b"dummy", bcrypt.gensalt())


@dataclass(frozen=True)
class User:
    """An authenticated person.

    Attributes:
        username: Unique login name.
        team: The single team the user belongs to.
    """

    username: str
    team: str


def _load(path: Path) -> list[dict[str, str]]:
    """Read and validate the password file (missing file means no users)."""
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text())
        if not isinstance(data, list):
            raise ValueError("top level must be a list")
        for entry in data:
            for key in ("username", "password_hash", "team"):
                if not isinstance(entry[key], str) or not entry[key]:
                    raise ValueError(f"bad or missing {key}")
    except (ValueError, KeyError, TypeError) as exc:
        raise ValueError(f"Malformed password file {path}: {exc}") from exc
    return data


class UserStore:
    """Read-only view of the password file, loaded once at construction."""

    def __init__(self, path: Path) -> None:
        """Load users from ``path``.

        Args:
            path: Password file location; a missing file yields an empty store.

        Raises:
            ValueError: If the file exists but is malformed.
        """
        self._entries = {e["username"]: e for e in _load(path)}

    def authenticate(self, username: str, password: str) -> User | None:
        """Check credentials.

        Args:
            username: Login name.
            password: Plaintext password to verify.

        Returns:
            The user on success, otherwise ``None``.
        """
        entry = self._entries.get(username)
        hashed = entry["password_hash"].encode() if entry else _DUMMY_HASH
        try:
            ok = bcrypt.checkpw(password.encode(), hashed)
        except ValueError:
            ok = False
        if entry is None or not ok:
            return None
        return User(entry["username"], entry["team"])

    def get(self, username: str) -> User | None:
        """Look up a user by name."""
        entry = self._entries.get(username)
        return User(entry["username"], entry["team"]) if entry else None

    def teams(self) -> list[str]:
        """Return the sorted distinct team names."""
        return sorted({e["team"] for e in self._entries.values()})

    def members(self, team: str) -> list[str]:
        """Return the sorted usernames on ``team``."""
        return sorted(u for u, e in self._entries.items() if e["team"] == team)


def add_user(path: Path, username: str, password: str, team: str) -> None:
    """Append a user with a bcrypt-hashed password to the password file.

    Args:
        path: Password file; created if absent.
        username: New unique username.
        password: Plaintext password (only its hash is stored).
        team: Team the user belongs to.

    Raises:
        ValueError: On blank fields or a duplicate username.
    """
    username, team = username.strip(), team.strip()
    if not username or not password or not team:
        raise ValueError("username, password and team must all be non-empty")
    entries = _load(path)
    if any(e["username"] == username for e in entries):
        raise ValueError(f"User {username!r} already exists")
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    entries.append({"username": username, "password_hash": hashed, "team": team})
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    with os.fdopen(fd, "w") as fh:
        json.dump(entries, fh, indent=2)
    os.replace(tmp, path)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point: ``add <username> <team>`` prompts for a password."""
    parser = argparse.ArgumentParser(prog="workboard.users")
    sub = parser.add_subparsers(dest="command", required=True)
    add = sub.add_parser("add", help="add a user")
    add.add_argument("username")
    add.add_argument("team")
    add.add_argument("--file", type=Path, default=Path("data/users.json"))
    args = parser.parse_args(argv)
    password = getpass.getpass("Password: ")
    try:
        add_user(args.file, args.username, password, args.team)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"Added {args.username} to team {args.team}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
