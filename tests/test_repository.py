import sqlite3
from pathlib import Path

import pytest

from workboard.repository import STATUSES, Repository


@pytest.fixture
def repo(tmp_path: Path) -> Repository:
    r = Repository(tmp_path / "w.db")
    r.init_schema()
    return r


def test_statuses_are_the_four_spec_values() -> None:
    assert STATUSES == ("New", "Planning", "In progress", "Finished")


def test_create_defaults_status_new_and_returns_item(repo: Repository) -> None:
    item = repo.create_item("red", "T", "D", "ann", "ann")
    assert item.id >= 1
    assert (item.team_id, item.title, item.description) == ("red", "T", "D")
    assert (item.assigned_to, item.status, item.created_by) == ("ann", "New", "ann")
    assert repo.get_item(item.id) == item


def test_list_items_only_returns_requested_team(repo: Repository) -> None:
    a = repo.create_item("red", "a", "", None, "ann")
    repo.create_item("blue", "b", "", None, "cy")
    assert [i.id for i in repo.list_items("red")] == [a.id]
    assert repo.list_items("green") == []


def test_update_changes_fields_and_bumps_updated_at(repo: Repository) -> None:
    item = repo.create_item("red", "T", "", None, "ann")
    updated = repo.update_item(item.id, status="Planning", assigned_to="bob", title="T2")
    assert updated is not None
    assert (updated.status, updated.assigned_to, updated.title) == ("Planning", "bob", "T2")
    assert updated.updated_at >= item.updated_at
    assert updated.created_at == item.created_at


def test_update_unknown_id_returns_none(repo: Repository) -> None:
    assert repo.update_item(999, status="Planning") is None


def test_update_unknown_field_raises(repo: Repository) -> None:
    item = repo.create_item("red", "T", "", None, "ann")
    with pytest.raises(ValueError):
        repo.update_item(item.id, team_id="blue")


def test_invalid_status_rejected_by_db(repo: Repository) -> None:
    item = repo.create_item("red", "T", "", None, "ann")
    with pytest.raises(sqlite3.IntegrityError):
        repo.update_item(item.id, status="Done")


def test_init_schema_is_idempotent(repo: Repository) -> None:
    item = repo.create_item("red", "T", "", None, "ann")
    repo.init_schema()
    assert repo.get_item(item.id) == item


def test_journal_mode_is_wal(repo: Repository, tmp_path: Path) -> None:
    with sqlite3.connect(tmp_path / "w.db") as conn:
        assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"


def test_assigned_to_can_be_set_to_none(repo: Repository) -> None:
    item = repo.create_item("red", "T", "", "ann", "ann")
    updated = repo.update_item(item.id, assigned_to=None)
    assert updated is not None and updated.assigned_to is None


def test_sql_injection_in_title_is_stored_literally(repo: Repository) -> None:
    evil = "x'); DROP TABLE work_items;--"
    item = repo.create_item("red", evil, "", None, "ann")
    assert repo.get_item(item.id).title == evil  # type: ignore[union-attr]
    assert len(repo.list_items("red")) == 1
