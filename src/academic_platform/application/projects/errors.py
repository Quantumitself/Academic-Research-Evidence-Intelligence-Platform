"""Typed errors for the research project service."""

from __future__ import annotations


class ProjectError(RuntimeError):
    """Base class for research project failures."""


class ProjectNotFoundError(ProjectError):
    """Raised when a project cannot be found by its key."""


class ProjectValidationError(ProjectError):
    """Raised when a project or its children fail validation.

    The error carries a list of issue messages so that the presentation
    layer can present them all at once rather than one per attempt.
    """

    def __init__(self, issues: list[str]) -> None:
        self.issues = tuple(issues)
        super().__init__("; ".join(self.issues) if self.issues else "validation failed")