"""Research-question development workspace.

This subpackage owns the persistent state and validation rules of the
research assistant's Research Questions section:

- ``QuestionKind`` — the closed set of question kinds the workspace
  supports.
- ``ResearchQuestionDraft`` — an immutable view of the workspace's
  current state.
- ``QuestionValidationReport`` — the validation report produced by the
  validator.
- ``ResearchQuestionWorkspaceService`` — the application service that
  reads and writes the draft, manages the primary question, and
  validates the draft against the specification's criteria.
- ``ResearchQuestionWorkspaceError`` and subclasses — typed errors.

The workspace is anchored to a research project. Questions are stored
in the ``research_question`` table. The distinction between the
question, the topic, the problem, and the gap is stored in the
project's ``project_metadata`` JSON column under a dedicated key, so
that the workspace can surface the reasoning the user has recorded.

The service never imports Qt. It reads and writes through the
research-question and research-project repositories, and writes audit
events through the audit repository.
"""

from academic_platform.application.research_questions.errors import (
    ResearchQuestionWorkspaceError,
    ResearchQuestionWorkspaceNotFoundError,
    ResearchQuestionWorkspaceValidationError,
)
from academic_platform.application.research_questions.model import (
    QuestionKind,
    QuestionValidationIssue,
    QuestionValidationReport,
    ResearchQuestionDraft,
    ResearchQuestionView,
)
from academic_platform.application.research_questions.service import (
    ResearchQuestionWorkspaceService,
)

__all__ = [
    "QuestionKind",
    "QuestionValidationIssue",
    "QuestionValidationReport",
    "ResearchQuestionDraft",
    "ResearchQuestionView",
    "ResearchQuestionWorkspaceError",
    "ResearchQuestionWorkspaceNotFoundError",
    "ResearchQuestionWorkspaceService",
    "ResearchQuestionWorkspaceValidationError",
]