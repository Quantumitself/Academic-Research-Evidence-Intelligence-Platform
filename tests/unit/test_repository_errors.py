"""Tests for the repository error hierarchy."""

from __future__ import annotations

from academic_platform.infrastructure.repositories.errors import (
    DuplicateEntityError,
    EntityNotFoundError,
    RepositoryError,
    RepositoryValidationError,
)


def test_hierarchy() -> None:
    assert issubclass(RepositoryError, RuntimeError)
    assert issubclass(EntityNotFoundError, RepositoryError)
    assert issubclass(DuplicateEntityError, RepositoryError)
    assert issubclass(RepositoryValidationError, RepositoryError)