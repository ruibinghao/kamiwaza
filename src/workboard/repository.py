"""SQLite persistence for work items. The only module that touches SQL."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

STATUSES: tuple[str, ...] = ("New", "Planning", "In progress", "Finished")
_UPDATABLE = {"title", "description", "assigned_to", "status"}
_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class WorkItem:
    """A single work item on a team's board."""

    id: int
    team_id: str
    title: str
    description: str
    assigned_to: str | None
    status: str
    created_by: str
    created_at: str
    updated_at: str


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="microseconds")


def _to_item(row: sqlite3.Row) -> WorkItem:
    return WorkItem(**{k: row[k] for k in row.keys()})  # noqa: SIM118


class Repository:
    """Data access for work items."""

    def __init__(self, db_path: Path) -> None:
        """Create a repository bound to ``db_path`` (file is created on first use)."""
        self._path = db_path

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._path, timeout=5)
        conn.row_factory = sqlite3.Row
        return conn

    def init_schema(self) -> None:
        """Create tables and indexes if absent; enable WAL. Safe to call repeatedly."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        statuses = ", ".join(f"'{s}'" for s in STATUSES)
        with closing(self._connect()) as conn, conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute(
                f"""CREATE TABLE IF NOT EXISTS work_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    team_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    assigned_to TEXT,
                    status TEXT NOT NULL DEFAULT 'New' CHECK (status IN ({statuses})),
                    created_by TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )"""
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_items_team_status ON work_items (team_id, status)"
            )
            conn.execute(f"PRAGMA user_version={_SCHEMA_VERSION}")

    def create_item(
        self,
        team_id: str,
        title: str,
        description: str,
        assigned_to: str | None,
        created_by: str,
    ) -> WorkItem:
        """Insert a new item with status ``New`` and return it."""
        now = _now()
        with closing(self._connect()) as conn, conn:
            cur = conn.execute(
                "INSERT INTO work_items (team_id, title, description, assigned_to, created_by,"
                " created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (team_id, title, description, assigned_to, created_by, now, now),
            )
            row = conn.execute("SELECT * FROM work_items WHERE id = ?", (cur.lastrowid,)).fetchone()
        return _to_item(row)

    def get_item(self, item_id: int) -> WorkItem | None:
        """Return the item with ``item_id`` or ``None``."""
        with closing(self._connect()) as conn:
            row = conn.execute("SELECT * FROM work_items WHERE id = ?", (item_id,)).fetchone()
        return _to_item(row) if row else None

    def list_items(self, team_id: str) -> list[WorkItem]:
        """Return all items of ``team_id`` ordered by id."""
        with closing(self._connect()) as conn:
            rows = conn.execute(
                "SELECT * FROM work_items WHERE team_id = ? ORDER BY id", (team_id,)
            ).fetchall()
        return [_to_item(r) for r in rows]

    def update_item(self, item_id: int, **fields: str | None) -> WorkItem | None:
        """Update allowed fields and bump ``updated_at``.

        Args:
            item_id: Item to change.
            **fields: Any of ``title``, ``description``, ``assigned_to``, ``status``.

        Returns:
            The updated item, or ``None`` if it does not exist.

        Raises:
            ValueError: If a field name is not updatable.
            sqlite3.IntegrityError: If ``status`` is not a valid status.
        """
        unknown = set(fields) - _UPDATABLE
        if unknown:
            raise ValueError(f"Cannot update fields: {sorted(unknown)}")
        columns = sorted(fields)
        assignments = ", ".join(f"{c} = ?" for c in columns) + (", " if columns else "")
        with closing(self._connect()) as conn, conn:
            cur = conn.execute(
                f"UPDATE work_items SET {assignments}updated_at = ? WHERE id = ?",
                (*(fields[c] for c in columns), _now(), item_id),
            )
            if cur.rowcount == 0:
                return None
            row = conn.execute("SELECT * FROM work_items WHERE id = ?", (item_id,)).fetchone()
        return _to_item(row)
