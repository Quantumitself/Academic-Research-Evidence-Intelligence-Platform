"""Typed errors for the Topic & Problem workspace."""

from __future__ import annotations


class TopicWorkspaceError(RuntimeError):
    """Base class for topic-workspace failures."""


class TopicWorkspaceNotFoundError(TopicWorkspaceError):
    """Raised when the attached project does not exist."""


class TopicWorkspaceNotAttachedError(TopicWorkspaceError):
    """Raised when the workspace is queried before a project is attached."""


class TopicWorkspaceValidationError(TopicWorkspaceError):
    """Raised when a field fails validation.

    The error carries a list of issue messages so that the presentation
    layer can present them all at once.
    """

    def __init__(self, issues: list[str]) -> None:
        self.issues = tuple(issues)
        super().__init__("; ".join(self.issues) if self.issues else "validation failed")