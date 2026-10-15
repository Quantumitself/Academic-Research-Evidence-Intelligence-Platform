"""Typed errors for the research task service."""

from __future__ import annotations


class TaskError(RuntimeError):
    """Base class for research task failures."""


class TaskNotFoundError(TaskError):
    """Raised when a task cannot be found by its identifier."""


class TaskValidationError(TaskError):
    """Raised when a task fails validation.

    The error carries a list of issue messages so that the presentation
    layer can present them all at once rather than one per attempt.
    """

    def __init__(self, issues: list[str]) -> None:
        self.issues = tuple(issues)
        super().__init__("; ".join(self.issues) if self.issues else "validation failed")