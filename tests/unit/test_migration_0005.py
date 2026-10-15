"""Tests for the migration that introduces search and publications."""

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
            "publication",
            "search_source",
            "saved_search_query",
            "search_session",
            "search_result",
        } <= names
    finally:
        database.dispose()


def test_downgrade_to_0004_drops_new_tables(database_url: str) -> None:
    upgrade_to_head(database_url)
    downgrade(database_url, "0004_document_assets")
    assert current_revision(database_url) == "0004_document_assets"
    database = _database_for(database_url)
    try:
        inspector = inspect(database.engine)
        names = set(inspector.get_table_names())
        assert "publication" not in names
        assert "search_source" not in names
        assert "saved_search_query" not in names
        assert "search_session" not in names
        assert "search_result" not in names
        assert "document_asset" in names
    finally:
        database.dispose()