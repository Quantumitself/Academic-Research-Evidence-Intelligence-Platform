"""Typed errors for smart-collection evaluation."""

from __future__ import annotations


class SmartCollectionError(RuntimeError):
    """Base class for smart-collection failures."""


class SmartCollectionFilterError(SmartCollectionError):
    """Raised when a filter payload cannot be parsed or validated.

    The error carries a list of issue messages so that the presentation
    layer can present them all at once.
    """

    def __init__(self, issues: list[str]) -> None:
        self.issues = tuple(issues)
        super().__init__("; ".join(self.issues) if self.issues else "invalid filter")