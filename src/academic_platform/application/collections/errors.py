"""Typed errors for the collection service."""

from __future__ import annotations


class CollectionError(RuntimeError):
    """Base class for collection failures."""


class CollectionNotFoundError(CollectionError):
    """Raised when a collection cannot be found by its key."""


class CollectionValidationError(CollectionError):
    """Raised when a collection or its items fail validation.

    The error carries a list of issue messages so that the presentation
    layer can present them all at once rather than one per attempt.
    """

    def __init__(self, issues: list[str]) -> None:
        self.issues = tuple(issues)
        super().__init__("; ".join(self.issues) if self.issues else "validation failed")