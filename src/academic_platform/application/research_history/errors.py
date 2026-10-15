"""Typed errors for the research-history workspace."""

from __future__ import annotations


class ResearchHistoryError(RuntimeError):
    """Base class for research-history failures."""


class ResearchHistoryNotFoundError(ResearchHistoryError):
    """Raised when the attached project or a history record is missing."""


class ResearchHistoryValidationError(ResearchHistoryError):
    """Raised when an input fails validation."""

    def __init__(self, issues: list[str]) -> None:
        self.issues = tuple(issues)
        super().__init__("; ".join(self.issues) if self.issues else "validation failed")


class ResearchHistorySearchError(ResearchHistoryError):
    """Raised when the search orchestration service fails.

    The error carries the per-source reports when available so that the
    presentation layer can surface the exact reason a source failed.
    """

    def __init__(self, message: str, *, source_reports: tuple = ()) -> None:
        super().__init__(message)
        self.source_reports = tuple(source_reports)