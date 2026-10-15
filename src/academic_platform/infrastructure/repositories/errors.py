"""Typed exceptions for the repository layer."""

from __future__ import annotations


class RepositoryError(RuntimeError):
    """Base class for repository-layer failures."""


class EntityNotFoundError(RepositoryError):
    """Raised when a requested entity does not exist."""


class DuplicateEntityError(RepositoryError):
    """Raised when a uniqueness constraint is violated by a create or update."""


class RepositoryValidationError(RepositoryError):
    """Raised when input fails validation before reaching the database."""