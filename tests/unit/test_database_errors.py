"""Tests for the database error hierarchy."""

from __future__ import annotations

from academic_platform.infrastructure.database import (
    DatabaseConfigurationError,
    DatabaseError,
)


def test_configuration_error_is_database_error() -> None:
    assert issubclass(DatabaseConfigurationError, DatabaseError)


def test_database_error_is_runtime_error() -> None:
    assert issubclass(DatabaseError, RuntimeError)