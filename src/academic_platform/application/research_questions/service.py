"""Application service for the research-question workspace.

The service is the single entry point the presentation layer uses to
manage the research-question draft. It:

- Reads and writes the topic, the problem, the gap, and the primary
  question on the attached research project.
- Manages the secondary questions and hypotheses through the
  research-question repository.
- Validates the draft against the specification's criteria and returns
  a structured report.
- Records an audit event for every mutation.

Design decisions
----------------
- The topic, the problem, and the gap are stored in the project's
  ``project_metadata`` JSON column under the ``research_question_workspace``
  key. The project's dedicated ``topic`` column carries the topic so
  that the topic remains visible in the projects page.
- The primary question is mirrored as a ``research_question`` row with
  the ``is_primary`` flag set, so that the question participates in the
  project's question list and in project export. The workspace also
  keeps a copy in the metadata so that the distinction between the
  primary question and secondary questions remains visible in the
  workspace's own view.
- Validation is fail-closed for inputs. The service validates its
  inputs and raises ``ResearchQuestionWorkspaceValidationError`` with
  every issue at once. The validation report is a separate operation
  that describes the state of a draft; it never blocks a write.
- The service never commits. It runs inside a unit of work supplied by
  the caller.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

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
from academic_platform.infrastructure.database.models import (
    AuditEvent,
    ResearchProject,
    ResearchQuestion,
)
from academic_platform.infrastructure.database.schemas import (
    ResearchProjectUpdate,
    ResearchQuestionCreate,
    ResearchQuestionUpdate,
)
from academic_platform.infrastructure.repositories.errors import (
    RepositoryError,
)
from academic_platform.infrastructure.repositories.manager import (
    RepositoryManager,
)

_logger = logging.getLogger(__name__)

_METADATA_KEY = "research_question_workspace"

_ACTION_WORKSPACE_UPDATED = "question.workspace_updated"
_ACTION_QUESTION_ADDED = "question.added"
_ACTION_QUESTION_UPDATED = "question.updated"
_ACTION_QUESTION_REMOVED = "question.removed"
_ACTION_PRIMARY_CHANGED = "question.primary_changed"

_TEXT_LIMIT = 4096
_QUESTION_LIMIT = 2048

_QUESTION_STARTERS = (
    "what",
    "which",
    "who",
    "whom",
    "whose",
    "where",
    "when",
    "why",
    "how",
    "does",
    "do",
    "is",
    "are",
    "was",
    "were",
    "can",
    "could",
    "should",
    "would",
    "will",
    "may",
    "might",
)

_VAGUE_TERMS = (
    "things",
    "stuff",
    "various",
    "several",
    "some",
    "many",
    "etc",
)


class ResearchQuestionWorkspaceService:
    """Application service for the research-question workspace."""

    def __init__(self, repositories: RepositoryManager) -> None:
        self._repositories = repositories
        self._project_key: str | None = None

    # ------------------------------------------------------------------
    # Attachment
    # ------------------------------------------------------------------
    def attach_project(self, project_key: str) -> ResearchQuestionDraft:
        """Attach the workspace to a project."""
        project = self._require_project(project_key)
        self._project_key = project_key
        self._sync_project_topic(project)
        return self.current_draft()

    @property
    def attached_project_key(self) -> str | None:
        return self._project_key

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------
    def current_draft(self) -> ResearchQuestionDraft:
        """Return the current workspace draft."""
        if self._project_key is None:
            return ResearchQuestionDraft(project_key=None)
        project = self._require_project(self._project_key)
        metadata = _parse_metadata(project.project_metadata)
        workspace = metadata.get(_METADATA_KEY, {})
        if not isinstance(workspace, dict):
            workspace = {}
        rows = self._list_questions(project.id)
        primary_text = workspace.get("primary_question") or ""
        # When the workspace has no stored primary text but a question
        # row is marked primary, use that row's text as the primary.
        if not primary_text:
            for row in rows:
                if row.is_primary:
                    primary_text = row.text
                    break
        views = tuple(_row_to_view(row) for row in rows)
        return ResearchQuestionDraft(
            project_key=self._project_key,
            primary_question=primary_text,
            topic=project.topic or "",
            problem=str(workspace.get("problem") or ""),
            gap=str(workspace.get("gap") or ""),
            questions=views,
        )
    def validation_report(self) -> QuestionValidationReport:
        """Return the validation report for the current draft."""
        return _validate(self.current_draft())

    # ------------------------------------------------------------------
    # Workspace field writes
    # ------------------------------------------------------------------
    def set_topic(self, topic: str) -> ResearchQuestionDraft:
        return self._set_workspace_field("topic", topic)

    def set_problem(self, problem: str) -> ResearchQuestionDraft:
        return self._set_workspace_field("problem", problem)

    def set_gap(self, gap: str) -> ResearchQuestionDraft:
        return self._set_workspace_field("gap", gap)

    def set_primary_question(self, text: str) -> ResearchQuestionDraft:
        """Set the primary question text and reflect it as a question row.

        The primary question is stored in the workspace metadata and
        mirrored as a ``research_question`` row with the ``is_primary``
        flag set. When a primary question row exists it is updated in
        place; otherwise a new row is created. Any other row marked
        primary is cleared.
        """
        cleaned = text.strip()
        if len(cleaned) > _QUESTION_LIMIT:
            raise ResearchQuestionWorkspaceValidationError(
                [f"Primary question must be at most {_QUESTION_LIMIT} characters"]
            )
        if self._project_key is None:
            raise ResearchQuestionWorkspaceNotAttachedError(
                "Cannot set the primary question without an attached project"
            )
        project = self._require_project(self._project_key)
        repo = self._repositories.get("research_question")
        rows = self._list_questions(project.id)
        primary_row: ResearchQuestion | None = None
        for row in rows:
            if row.is_primary:
                primary_row = row
                break
        try:
            if cleaned:
                if primary_row is None:
                    repo.create(
                        ResearchQuestionCreate(
                            project_id=project.id,
                            text=cleaned,
                            kind=QuestionKind.MAIN.value,
                            is_primary=True,
                            position=len(rows),
                        )
                    )
                else:
                    repo.clear_primary_for_project(project.id)
                    repo.update(
                        primary_row,
                        ResearchQuestionUpdate(
                            text=cleaned,
                            kind=QuestionKind.MAIN.value,
                            is_primary=True,
                        ),
                    )
            elif primary_row is not None:
                repo.update(
                    primary_row,
                    ResearchQuestionUpdate(is_primary=False),
                )
            metadata = _parse_metadata(project.project_metadata)
            workspace = metadata.get(_METADATA_KEY)
            if not isinstance(workspace, dict):
                workspace = {}
            if cleaned:
                workspace["primary_question"] = cleaned
            else:
                workspace.pop("primary_question", None)
            self._write_metadata(project, metadata, workspace)
        except RepositoryError as exc:
            raise ResearchQuestionWorkspaceError(
                f"Unable to set the primary question: {exc}"
            ) from exc
        self._record_audit(
            action=_ACTION_PRIMARY_CHANGED,
            summary=(
                f"Primary question set to {cleaned[:80]!r}"
                if cleaned
                else "Primary question cleared"
            ),
        )
        return self.current_draft()

    # ------------------------------------------------------------------
    # Question management
    # ------------------------------------------------------------------
    def add_question(
        self,
        text: str,
        *,
        kind: QuestionKind = QuestionKind.SUB,
        is_primary: bool = False,
    ) -> ResearchQuestionView:
        """Add a secondary question or hypothesis."""
        cleaned = text.strip()
        if not cleaned:
            raise ResearchQuestionWorkspaceValidationError(
                ["Question text must not be empty"]
            )
        if len(cleaned) > _QUESTION_LIMIT:
            raise ResearchQuestionWorkspaceValidationError(
                [f"Question must be at most {_QUESTION_LIMIT} characters"]
            )
        if self._project_key is None:
            raise ResearchQuestionWorkspaceNotAttachedError(
                "Cannot add a question without an attached project"
            )
        project = self._require_project(self._project_key)
        repo = self._repositories.get("research_question")
        rows = self._list_questions(project.id)
        if is_primary:
            try:
                repo.clear_primary_for_project(project.id)
            except RepositoryError:
                pass
        try:
            row = repo.create(
                ResearchQuestionCreate(
                    project_id=project.id,
                    text=cleaned,
                    kind=kind.value,
                    is_primary=is_primary,
                    position=len(rows),
                )
            )
        except RepositoryError as exc:
            raise ResearchQuestionWorkspaceError(
                f"Unable to add the question: {exc}"
            ) from exc
        self._record_audit(
            action=_ACTION_QUESTION_ADDED,
            summary=f"Added {kind.display_name.lower()} {cleaned[:80]!r}",
        )
        return _row_to_view(row)

    def update_question(
        self,
        question_id: int,
        *,
        text: str | None = None,
        kind: QuestionKind | None = None,
    ) -> ResearchQuestionView:
        """Update a question's text or kind."""
        if self._project_key is None:
            raise ResearchQuestionWorkspaceNotAttachedError(
                "Cannot update a question without an attached project"
            )
        project = self._require_project(self._project_key)
        repo = self._repositories.get("research_question")
        try:
            row = repo.get(question_id)
        except RepositoryError as exc:
            raise ResearchQuestionWorkspaceError(
                f"Unable to read the question: {exc}"
            ) from exc
        if row is None or row.project_id != project.id:
            raise ResearchQuestionWorkspaceNotFoundError(
                f"No question with id {question_id!r} in project "
                f"{self._project_key!r}"
            )
        changes: dict[str, Any] = {}
        if text is not None:
            cleaned = text.strip()
            if not cleaned:
                raise ResearchQuestionWorkspaceValidationError(
                    ["Question text must not be empty"]
                )
            if len(cleaned) > _QUESTION_LIMIT:
                raise ResearchQuestionWorkspaceValidationError(
                    [f"Question must be at most {_QUESTION_LIMIT} characters"]
                )
            changes["text"] = cleaned
        if kind is not None:
            changes["kind"] = kind.value
        if not changes:
            return _row_to_view(row)
        try:
            updated = repo.update(row, ResearchQuestionUpdate(**changes))
        except RepositoryError as exc:
            raise ResearchQuestionWorkspaceError(
                f"Unable to update the question: {exc}"
            ) from exc
        self._record_audit(
            action=_ACTION_QUESTION_UPDATED,
            summary=f"Updated question {updated.text[:80]!r}",
        )
        return _row_to_view(updated)

    def remove_question(self, question_id: int) -> None:
        """Remove a question."""
        if self._project_key is None:
            raise ResearchQuestionWorkspaceNotAttachedError(
                "Cannot remove a question without an attached project"
            )
        project = self._require_project(self._project_key)
        repo = self._repositories.get("research_question")
        try:
            row = repo.get(question_id)
        except RepositoryError as exc:
            raise ResearchQuestionWorkspaceError(
                f"Unable to read the question: {exc}"
            ) from exc
        if row is None or row.project_id != project.id:
            raise ResearchQuestionWorkspaceNotFoundError(
                f"No question with id {question_id!r} in project "
                f"{self._project_key!r}"
            )
        was_primary = bool(row.is_primary)
        try:
            repo.delete(row)
        except RepositoryError as exc:
            raise ResearchQuestionWorkspaceError(
                f"Unable to remove the question: {exc}"
            ) from exc
        if was_primary:
            # Clear the metadata primary text as well, since the row
            # that supported it no longer exists.
            metadata = _parse_metadata(project.project_metadata)
            workspace = metadata.get(_METADATA_KEY)
            if isinstance(workspace, dict):
                workspace.pop("primary_question", None)
                try:
                    self._write_metadata(project, metadata, workspace)
                except ResearchQuestionWorkspaceError:
                    _logger.warning(
                        "Unable to clear the workspace primary question"
                    )
        self._record_audit(
            action=_ACTION_QUESTION_REMOVED,
            summary=f"Removed question {row.text[:80]!r}",
        )

    def promote_to_primary(self, question_id: int) -> ResearchQuestionView:
        """Designate a question as the project's primary question."""
        if self._project_key is None:
            raise ResearchQuestionWorkspaceNotAttachedError(
                "Cannot promote a question without an attached project"
            )
        project = self._require_project(self._project_key)
        repo = self._repositories.get("research_question")
        try:
            row = repo.get(question_id)
        except RepositoryError as exc:
            raise ResearchQuestionWorkspaceError(
                f"Unable to read the question: {exc}"
            ) from exc
        if row is None or row.project_id != project.id:
            raise ResearchQuestionWorkspaceNotFoundError(
                f"No question with id {question_id!r} in project "
                f"{self._project_key!r}"
            )
        try:
            repo.clear_primary_for_project(project.id)
            updated = repo.update(
                row, ResearchQuestionUpdate(is_primary=True)
            )
        except RepositoryError as exc:
            raise ResearchQuestionWorkspaceError(
                f"Unable to promote the question: {exc}"
            ) from exc
        metadata = _parse_metadata(project.project_metadata)
        workspace = metadata.get(_METADATA_KEY)
        if not isinstance(workspace, dict):
            workspace = {}
        workspace["primary_question"] = updated.text
        try:
            self._write_metadata(project, metadata, workspace)
        except ResearchQuestionWorkspaceError:
            _logger.warning(
                "Unable to mirror the promoted primary question"
            )
        self._record_audit(
            action=_ACTION_PRIMARY_CHANGED,
            summary=f"Primary question set to {updated.text[:80]!r}",
        )
        return _row_to_view(updated)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _set_workspace_field(self, field_name: str, value: str) -> ResearchQuestionDraft:
        if self._project_key is None:
            raise ResearchQuestionWorkspaceNotAttachedError(
                "Cannot write without an attached project"
            )
        cleaned = value.strip() if isinstance(value, str) else ""
        if len(cleaned) > _TEXT_LIMIT:
            raise ResearchQuestionWorkspaceValidationError(
                [
                    f"{field_name.capitalize()} must be at most "
                    f"{_TEXT_LIMIT} characters"
                ]
            )
        project = self._require_project(self._project_key)
        metadata = _parse_metadata(project.project_metadata)
        workspace = metadata.get(_METADATA_KEY)
        if not isinstance(workspace, dict):
            workspace = {}
        if cleaned:
            workspace[field_name] = cleaned
        else:
            workspace.pop(field_name, None)
        try:
            self._write_metadata(project, metadata, workspace)
        except ResearchQuestionWorkspaceError:
            raise
        self._record_audit(
            action=_ACTION_WORKSPACE_UPDATED,
            summary=f"Updated {field_name}",
        )
        return self.current_draft()

    def _write_metadata(
        self,
        project: ResearchProject,
        metadata: dict,
        workspace: dict,
    ) -> None:
        if workspace:
            metadata[_METADATA_KEY] = workspace
        else:
            metadata.pop(_METADATA_KEY, None)
        payload = ResearchProjectUpdate(
            project_metadata=(
                json.dumps(metadata, sort_keys=True) if metadata else None
            )
        )
        try:
            self._repositories.get("research_project").update(project, payload)
        except RepositoryError as exc:
            raise ResearchQuestionWorkspaceError(
                f"Unable to persist the workspace: {exc}"
            ) from exc

    def _sync_project_topic(self, project: ResearchProject) -> None:
        # The topic lives on the project's dedicated column. When the
        # workspace is attached, the topic is mirrored into the
        # workspace metadata so that it is visible through the draft.
        # No write is required; the draft reads the project's column.
        _ = project

    def _list_questions(self, project_id: int) -> list[ResearchQuestion]:
        repo = self._repositories.get("research_question")
        try:
            return list(repo.list_for_project(project_id))
        except RepositoryError as exc:
            raise ResearchQuestionWorkspaceError(
                f"Unable to list questions: {exc}"
            ) from exc

    def _require_project(self, key: str) -> ResearchProject:
        repo = self._repositories.get("research_project")
        try:
            row = repo.find_by_key(key)
        except RepositoryError as exc:
            raise ResearchQuestionWorkspaceError(
                f"Unable to read the project: {exc}"
            ) from exc
        if row is None:
            raise ResearchQuestionWorkspaceNotFoundError(
                f"No project with key {key!r}"
            )
        return row

    def _record_audit(self, *, action: str, summary: str) -> None:
        try:
            session = self._repositories.get("audit_event").session
            session.add(
                AuditEvent(
                    actor="system",
                    action=action,
                    target_type="research_project",
                    target_identifier=self._project_key or "",
                    summary=summary,
                )
            )
            session.flush()
        except Exception as exc:  # noqa: BLE001 - boundary
            _logger.warning("Unable to record the audit event: %s", exc)


class ResearchQuestionWorkspaceNotAttachedError(ResearchQuestionWorkspaceError):
    """Raised when a write is attempted without an attached project."""


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
def _parse_metadata(raw: str | None) -> dict:
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except ValueError:
        return {}
    if not isinstance(parsed, dict):
        return {}
    return dict(parsed)


def _row_to_view(row: ResearchQuestion) -> ResearchQuestionView:
    try:
        kind = QuestionKind(row.kind)
    except ValueError:
        kind = QuestionKind.SUB
    return ResearchQuestionView(
        identifier=row.id,
        text=row.text,
        kind=kind,
        is_primary=bool(row.is_primary),
        position=row.position,
        created_at=row.created_at.isoformat() if row.created_at else "",
        updated_at=row.updated_at.isoformat() if row.updated_at else "",
    )


def _validate(draft: ResearchQuestionDraft) -> QuestionValidationReport:
    issues: list[QuestionValidationIssue] = []
    score = 0.0

    if not draft.primary_question.strip():
        issues.append(
            QuestionValidationIssue(
                severity="error",
                field="primary_question",
                message=(
                    "A primary research question is required before the "
                    "study can proceed."
                ),
            )
        )
    else:
        score += 0.3
        issues.extend(_validate_question_text(
            draft.primary_question, field="primary_question"
        ))

    if not draft.topic.strip():
        issues.append(
            QuestionValidationIssue(
                severity="warning",
                field="topic",
                message=(
                    "The topic is not recorded. The topic helps bound the "
                    "research question."
                ),
            )
        )
    else:
        score += 0.15

    if not draft.problem.strip():
        issues.append(
            QuestionValidationIssue(
                severity="warning",
                field="problem",
                message=(
                    "The research problem is not recorded. The problem "
                    "justifies the study and shapes the question."
                ),
            )
        )
    else:
        score += 0.15

    if not draft.gap.strip():
        issues.append(
            QuestionValidationIssue(
                severity="warning",
                field="gap",
                message=(
                    "The knowledge gap is not recorded. The gap positions "
                    "the study against the literature."
                ),
            )
        )
    else:
        score += 0.15

    if draft.question_count == 0:
        issues.append(
            QuestionValidationIssue(
                severity="warning",
                field="questions",
                message=(
                    "No secondary questions or hypotheses are recorded. "
                    "They are not always required, but they make the "
                    "study's scope explicit."
                ),
            )
        )
    else:
        score += 0.1

    if any(question.is_primary for question in draft.questions):
        score += 0.15

    score = max(0.0, min(1.0, score))
    return QuestionValidationReport(issues=tuple(issues), score=round(score, 3))


def _validate_question_text(
    text: str,
    *,
    field: str,
) -> list[QuestionValidationIssue]:
    issues: list[QuestionValidationIssue] = []
    stripped = text.strip()
    if not stripped:
        issues.append(
            QuestionValidationIssue(
                severity="error",
                field=field,
                message="The question must not be empty.",
            )
        )
        return issues
    lowered = stripped.lower()
    if not stripped.endswith("?"):
        issues.append(
            QuestionValidationIssue(
                severity="warning",
                field=field,
                message=(
                    "The question does not end with a question mark. "
                    "Consider phrasing it as a question."
                ),
            )
        )
    first_token = re.split(r"\s+", lowered, maxsplit=1)[0]
    if first_token not in _QUESTION_STARTERS:
        issues.append(
            QuestionValidationIssue(
                severity="warning",
                field=field,
                message=(
                    "The question does not start with an interrogative "
                    "word. Consider rewriting it as a question."
                ),
            )
        )
    for vague in _VAGUE_TERMS:
        if re.search(rf"\b{re.escape(vague)}\b", lowered):
            issues.append(
                QuestionValidationIssue(
                    severity="warning",
                    field=field,
                    message=(
                        f"The question contains the vague term {vague!r}. "
                        "Consider replacing it with a specific term."
                    ),
                )
            )
            break
    word_count = len(stripped.split())
    if word_count < 4:
        issues.append(
            QuestionValidationIssue(
                severity="warning",
                field=field,
                message=(
                    "The question is very short. A focused question "
                    "usually names the population, the variables, and the "
                    "context."
                ),
            )
        )
    elif word_count > 60:
        issues.append(
            QuestionValidationIssue(
                severity="warning",
                field=field,
                message=(
                    "The question is very long. Consider splitting it "
                    "into a primary question and one or more "
                    "sub-questions."
                ),
            )
        )
    return issues