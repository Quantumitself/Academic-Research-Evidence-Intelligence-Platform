"""Tests for the programmatic migration runner."""

from __future__ import annotations

from pathlib import Path

import pytest

from academic_platform.infrastructure.database.migrations import (
    DatabaseMigrationError,
    current_revision,
    head_revision,
    upgrade_to_head,
)
from tests.unit._migration_head import EXPECTED_HEAD



@pytest.fixture()
def database_url(tmp_path: Path) -> str:
    target = tmp_path / "app.sqlite3"
    target.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{target.as_posix()}"


def test_upgrade_from_empty_database(database_url: str) -> None:
    result = upgrade_to_head(database_url)
    assert result.previous_revision is None
    assert result.current_revision == EXPECTED_HEAD
    assert result.head_revision == EXPECTED_HEAD
    assert result.changed is True
    assert result.up_to_date is True


def test_upgrade_is_idempotent(database_url: str) -> None:
    first = upgrade_to_head(database_url)
    second = upgrade_to_head(database_url)
    assert first.current_revision == second.current_revision
    assert second.changed is False
    assert second.up_to_date is True


def test_current_revision_returns_none_for_unmigrated(database_url: str) -> None:
    assert current_revision(database_url) is None


def test_current_revision_after_upgrade(database_url: str) -> None:
    upgrade_to_head(database_url)
    assert current_revision(database_url) == EXPECTED_HEAD


def test_head_revision_matches_baseline(database_url: str) -> None:
    assert head_revision(database_url) == EXPECTED_HEAD


def test_missing_alembic_ini_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from academic_platform.infrastructure.database import migrations as migrations_module

    monkeypatch.setattr(
        migrations_module,
        "_ALEMBIC_INI",
        tmp_path / "does-not-exist.ini",
    )
    with pytest.raises(DatabaseMigrationError):
        upgrade_to_head("sqlite://")