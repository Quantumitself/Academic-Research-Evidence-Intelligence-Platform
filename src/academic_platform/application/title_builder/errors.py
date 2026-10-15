"""Typed errors for the title builder."""

from __future__ import annotations


class TitleBuilderError(RuntimeError):
    """Base class for title-builder failures."""


class TitleBuilderNotFoundError(TitleBuilderError):
    """Raised when the attached project or a title candidate is missing."""


class TitleBuilderValidationError(TitleBuilderError):
    """Raised when an input fails validation.

    The error carries a list of issue messages so that the presentation
    layer can present them all at once.
    """

    def __init__(self, issues: list[str]) -> None:
        self.issues = tuple(issues)
        super().__init__("; ".join(self.issues) if self.issues else "validation failed")