"""Tests for the database configuration value object."""

from __future__ import annotations

from pathlib import Path

import pytest

from academic_platform.infrastructure.database import (
    DatabaseConfiguration,
    DatabaseConfigurationError,
)


def test_file_url_built_from_path(tmp_path: Path) -> None:
    target = tmp_path / "app.sqlite3"
    config = DatabaseConfiguration.for_file(target)
    assert config.url.startswith("sqlite:///")
    assert str(target.resolve().as_posix()) in config.url
    assert config.database_path == target.resolve()


def test_memory_url_and_flag() -> None:
    config = DatabaseConfiguration.for_memory()
    assert config.is_memory
    assert config.database_path is None
    assert config.journal_mode == "MEMORY"


def test_empty_url_rejected() -> None:
    with pytest.raises(DatabaseConfigurationError):
        DatabaseConfiguration(url="")


def test_unsupported_scheme_rejected() -> None:
    with pytest.raises(DatabaseConfigurationError):
        DatabaseConfiguration(url="postgresql://localhost/app")


def test_negative_busy_timeout_rejected() -> None:
    with pytest.raises(DatabaseConfigurationError):
        DatabaseConfiguration(url="sqlite://", busy_timeout_ms=0)


def test_invalid_journal_mode_rejected() -> None:
    with pytest.raises(DatabaseConfigurationError):
        DatabaseConfiguration(url="sqlite://", journal_mode="bogus")


def test_invalid_synchronous_rejected() -> None:
    with pytest.raises(DatabaseConfigurationError):
        DatabaseConfiguration(url="sqlite://", synchronous="bogus")


def test_file_url_scheme_detected() -> None:
    config = DatabaseConfiguration(url="sqlite:///tmp/x.sqlite3")
    assert not config.is_memory