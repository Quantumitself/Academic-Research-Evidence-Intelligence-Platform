"""Tests for the migration that introduces document assets."""

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
            "document_asset",
            "document_metadata",
            "document_chunk",
            "annotation",
        } <= names
    finally:
        database.dispose()


def test_downgrade_to_0003_drops_new_tables(database_url: str) -> None:
    upgrade_to_head(database_url)
    downgrade(database_url, "0003_projects_and_collections")
    assert current_revision(database_url) == "0003_projects_and_collections"
    database = _database_for(database_url)
    try:
        inspector = inspect(database.engine)
        names = set(inspector.get_table_names())
        assert "document_asset" not in names
        assert "document_metadata" not in names
        assert "document_chunk" not in names
        assert "annotation" not in names
        assert "research_project" in names
    finally:
        database.dispose()