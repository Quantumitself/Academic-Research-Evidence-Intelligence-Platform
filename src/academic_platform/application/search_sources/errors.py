"""Typed errors for the search source registry service."""

from __future__ import annotations


class SourceError(RuntimeError):
    """Base class for search source service failures."""


class SourceNotFoundError(SourceError):
    """Raised when a source is not found by key or identifier."""


class SourceValidationError(SourceError):
    """Raised when a source configuration fails validation.

    The error carries a list of issue messages so that the presentation
    layer can display them all at once rather than one per attempt.
    """

    def __init__(self, issues: list[str]) -> None:
        self.issues = tuple(issues)
        super().__init__("; ".join(self.issues) if self.issues else "validation failed")