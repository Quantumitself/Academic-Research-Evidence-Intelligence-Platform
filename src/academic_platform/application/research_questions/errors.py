"""Typed errors for the research-question workspace."""

from __future__ import annotations


class ResearchQuestionWorkspaceError(RuntimeError):
    """Base class for research-question workspace failures."""


class ResearchQuestionWorkspaceNotFoundError(ResearchQuestionWorkspaceError):
    """Raised when the attached project or a question is missing."""


class ResearchQuestionWorkspaceValidationError(ResearchQuestionWorkspaceError):
    """Raised when an input fails validation.

    The error carries a list of issue messages so that the presentation
    layer can present them all at once.
    """

    def __init__(self, issues: list[str]) -> None:
        self.issues = tuple(issues)
        super().__init__("; ".join(self.issues) if self.issues else "validation failed")