"""Tests for the migration that introduces projects and collections."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import inspect

from academic_platform.infrastructure.database import (
    Database,
    DatabaseConfiguration,
)
from academic_platform.infrastructure.database.migrations import (
    current_revision,
    downgrade,
    upgrade_to_head,
)
from tests.unit._migration_head import EXPECTED_HEAD


@pytest.fixture()
def database_url(tmp_path: Path) -> str:
    target = tmp_path / "app.sqlite3"
    target.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{target.as_posix()}"


def _database_for(url: str) -> Database:
    return Database(DatabaseConfiguration(url=url))


def test_upgrade_reaches_head(database_url: str) -> None:
    result = upgrade_to_head(database_url)
    assert result.current_revision == EXPECTED_HEAD
    assert result.head_revision == EXPECTED_HEAD


def test_tables_created(database_url: str) -> None:
    upgrade_to_head(database_url)
    database = _database_for(database_url)
    try:
        inspector = inspect(database.engine)
        names = set(inspector.get_table_names())
        assert {
            "research_project",
            "research_question",
            "collection",
            "collection_item",
        } <= names
    finally:
        database.dispose()


def test_downgrade_to_0002_drops_new_tables(database_url: str) -> None:
    upgrade_to_head(database_url)
    downgrade(database_url, "0002_user_profile_settings_audit")
    assert current_revision(database_url) == "0002_user_profile_settings_audit"
    database = _database_for(database_url)
    try:
        inspector = inspect(database.engine)
        names = set(inspector.get_table_names())
        assert "research_project" not in names
        assert "research_question" not in names
        assert "collection" not in names
        assert "collection_item" not in names
        assert "user_profile" in names
    finally:
        database.dispose()