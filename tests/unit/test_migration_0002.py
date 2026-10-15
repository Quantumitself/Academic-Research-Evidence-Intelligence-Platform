"""Tests for the migration that introduces the first application tables."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import inspect

from academic_platform.infrastructure.database import Database
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


def test_upgrade_reaches_head(database_url: str) -> None:
    result = upgrade_to_head(database_url)
    assert result.current_revision == EXPECTED_HEAD
    assert result.head_revision == EXPECTED_HEAD


def test_tables_created(database_url: str) -> None:
    upgrade_to_head(database_url)
    database = Database(database_configuration_for(database_url))
    try:
        inspector = inspect(database.engine)
        names = set(inspector.get_table_names())
        assert {"user_profile", "app_settings", "audit_event"} <= names
    finally:
        database.dispose()


def test_downgrade_to_baseline_drops_tables(database_url: str) -> None:
    upgrade_to_head(database_url)
    downgrade(database_url, "0001_baseline")
    assert current_revision(database_url) == "0001_baseline"
    database = Database(database_configuration_for(database_url))
    try:
        inspector = inspect(database.engine)
        names = set(inspector.get_table_names())
        assert "user_profile" not in names
        assert "app_settings" not in names
        assert "audit_event" not in names
    finally:
        database.dispose()


def test_downgrade_all_the_way_to_base(database_url: str) -> None:
    upgrade_to_head(database_url)
    downgrade(database_url, "base")
    assert current_revision(database_url) is None


# Local helper: build a ``DatabaseConfiguration`` from a URL. The Database
# constructor accepts a configuration, not a URL, so a small adapter is
# used here rather than exposing a new constructor on Database.
def database_configuration_for(url: str):
    from academic_platform.infrastructure.database import DatabaseConfiguration

    return DatabaseConfiguration(url=url)