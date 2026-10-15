"""Application service for the Topic & Problem workspace.

The service anchors the topic draft to a research project. It reads the
project's existing topic fields, merges them with the workspace's
extended fields, and writes the merged result through the research
project repository.

Design decisions
----------------
- The workspace stores its extended fields in the project's
  ``project_metadata`` JSON column. The project's dedicated ``topic``
  column carries the broad subject, so that the topic remains visible
  in the projects page without decoding JSON.
- The service never mutates a project that does not exist. It raises
  ``TopicWorkspaceNotFoundError`` when the attached project cannot be
  found.
- The service validates every write. Fields are bounded to a
  documented maximum length; empty values are permitted because a
  draft is filled incrementally.
- The service never commits. It runs inside a unit of work supplied by
  the caller.
- Every successful write records an audit event.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from academic_platform.application.topic_workspace.errors import (
    TopicWorkspaceError,
    TopicWorkspaceNotFoundError,
    TopicWorkspaceNotAttachedError,
    TopicWorkspaceValidationError,
)
from academic_platform.application.topic_workspace.model import (
    ESSENTIAL_FIELDS,
    TopicCompleteness,
    TopicDraft,
    TopicField,
)
from academic_platform.infrastructure.database.models import (
    AuditEvent,
    ResearchProject,
)
from academic_platform.infrastructure.database.schemas import (
    ResearchProjectUpdate,
)
from academic_platform.infrastructure.repositories.errors import (
    RepositoryError,
)
from academic_platform.infrastructure.repositories.manager import (
    RepositoryManager,
)

_logger = logging.getLogger(__name__)

_METADATA_KEY = "topic_workspace"

_FIELD_MAX_LENGTHS: dict[TopicField, int] = {
    TopicField.BROAD_SUBJECT: 1024,
    TopicField.RESEARCH_PROBLEM: 4096,
    TopicField.CONTEXT: 2048,
    TopicField.POPULATION: 1024,
    TopicField.TIME_PERIOD: 256,
    TopicField.KEY_CONCEPTS: 2048,
    TopicField.POTENTIAL_OUTCOMES: 2048,
    TopicField.CONSTRAINTS: 2048,
    TopicField.KNOWLEDGE_LEVEL: 512,
}

_ACTION_TOPIC_CREATED = "topic.created"
_ACTION_TOPIC_UPDATED = "topic.updated"
_ACTION_TOPIC_CLEARED = "topic.cleared"
_ACTION_TOPIC_ATTACHED = "topic.attached"
_ACTION_TOPIC_DETACHED = "topic.detached"


class TopicWorkspaceService:
    """Application service for the Topic & Problem workspace."""

    def __init__(self, repositories: RepositoryManager) -> None:
        self._repositories = repositories
        self._project_key: str | None = None
        self._draft: dict[str, str] = {}

    # ------------------------------------------------------------------
    # Attachment
    # ------------------------------------------------------------------
    def attach_project(self, project_key: str, *, actor: str = "system") -> TopicDraft:
        """Attach the workspace to a project.

        The project's existing topic fields are read into the workspace.
        Any unsaved draft that was present before the attachment is
        discarded; callers that want to merge should call
        ``merge_into_project`` explicitly.

        Raises
        ------
        TopicWorkspaceNotFoundError
            If the project does not exist.
        """
        project = self._require_project(project_key)
        self._project_key = project_key
        self._draft = self._read_project_fields(project)
        self._record_audit(
            actor=actor,
            action=_ACTION_TOPIC_ATTACHED,
            target_identifier=project_key,
            summary=f"Workspace attached to {project.key!r}",
        )
        return self._build_draft()

    def detach_project(self, *, actor: str = "system") -> TopicDraft:
        """Detach the workspace from its project.

        The workspace reverts to an unattached draft that holds the
        current values, so that the user can continue editing without
        losing their work.
        """
        if self._project_key is not None:
            self._record_audit(
                actor=actor,
                action=_ACTION_TOPIC_DETACHED,
                target_identifier=self._project_key,
                summary=f"Workspace detached from {self._project_key!r}",
            )
        self._project_key = None
        return self._build_draft()

    @property
    def attached_project_key(self) -> str | None:
        return self._project_key

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------
    def current_draft(self) -> TopicDraft:
        """Return the current workspace draft."""
        return self._build_draft()

    def field_value(self, field: TopicField) -> str:
        """Return the current value of a field."""
        return self._draft.get(field.value, "")

    def completeness(self) -> TopicCompleteness:
        """Return the completeness report for the current draft."""
        return _compute_completeness(self._draft)

    # ------------------------------------------------------------------
    # Writes
    # ------------------------------------------------------------------
    def set_field(
        self,
        field: TopicField,
        value: str,
        *,
        actor: str = "system",
    ) -> TopicDraft:
        """Set a single field and persist the change if a project is attached."""
        self._validate_field(field, value)
        self._draft[field.value] = value
        if self._project_key is not None:
            self._persist_to_project(actor=actor, action=_ACTION_TOPIC_UPDATED)
        return self._build_draft()

    def set_fields(
        self,
        values: dict[TopicField, str],
        *,
        actor: str = "system",
    ) -> TopicDraft:
        """Set multiple fields at once and persist the change."""
        issues: list[str] = []
        for field, value in values.items():
            try:
                self._validate_field(field, value)
            except TopicWorkspaceValidationError as exc:
                issues.extend(exc.issues)
        if issues:
            raise TopicWorkspaceValidationError(issues)
        for field, value in values.items():
            self._draft[field.value] = value
        if self._project_key is not None:
            self._persist_to_project(actor=actor, action=_ACTION_TOPIC_UPDATED)
        return self._build_draft()

    def clear(self, *, actor: str = "system") -> TopicDraft:
        """Clear every field.

        When a project is attached, the project's topic column and the
        workspace metadata are cleared as well.
        """
        self._draft = {}
        if self._project_key is not None:
            self._persist_to_project(actor=actor, action=_ACTION_TOPIC_CLEARED)
        return self._build_draft()

    def merge_into_project(
        self,
        project_key: str,
        *,
        actor: str = "system",
    ) -> TopicDraft:
        """Attach the workspace to a project and merge the draft's values.

        Fields present in the draft overwrite the project's current
        values. Fields absent from the draft are left unchanged.
        """
        project = self._require_project(project_key)
        existing = self._read_project_fields(project)
        merged = dict(existing)
        for key, value in self._draft.items():
            if value.strip():
                merged[key] = value
        self._project_key = project_key
        self._draft = merged
        self._persist_to_project(actor=actor, action=_ACTION_TOPIC_UPDATED)
        return self._build_draft()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _build_draft(self) -> TopicDraft:
        return TopicDraft(
            project_key=self._project_key,
            values=dict(self._draft),
        )

    def _validate_field(self, field: TopicField, value: str) -> None:
        issues: list[str] = []
        if not isinstance(field, TopicField):
            raise TopicWorkspaceValidationError(
                [f"Unknown topic field: {field!r}"]
            )
        limit = _FIELD_MAX_LENGTHS.get(field, 4096)
        if isinstance(value, str) and len(value) > limit:
            issues.append(
                f"{field.display_name} must be at most {limit} characters"
            )
        if not isinstance(value, str):
            issues.append(f"{field.display_name} must be a string")
        if issues:
            raise TopicWorkspaceValidationError(issues)

    def _require_project(self, key: str) -> ResearchProject:
        repo = self._repositories.get("research_project")
        try:
            row = repo.find_by_key(key)
        except RepositoryError as exc:
            raise TopicWorkspaceError(
                f"Unable to read the project: {exc}"
            ) from exc
        if row is None:
            raise TopicWorkspaceNotFoundError(
                f"No project with key {key!r}"
            )
        return row

    def _read_project_fields(self, project: ResearchProject) -> dict[str, str]:
        values: dict[str, str] = {}
        # The project's dedicated ``topic`` column carries the broad
        # subject so that the subject is visible in the projects page.
        if project.topic:
            values[TopicField.BROAD_SUBJECT.value] = project.topic
        metadata = _parse_metadata(project.project_metadata)
        workspace = metadata.get(_METADATA_KEY)
        if isinstance(workspace, dict):
            for field in TopicField:
                candidate = workspace.get(field.value)
                if isinstance(candidate, str) and candidate.strip():
                    values[field.value] = candidate
        return values

    def _persist_to_project(self, *, actor: str, action: str) -> None:
        if self._project_key is None:
            raise TopicWorkspaceNotAttachedError(
                "Cannot persist without an attached project"
            )
        repo = self._repositories.get("research_project")
        try:
            project = repo.find_by_key(self._project_key)
        except RepositoryError as exc:
            raise TopicWorkspaceError(
                f"Unable to read the project: {exc}"
            ) from exc
        if project is None:
            raise TopicWorkspaceNotFoundError(
                f"No project with key {self._project_key!r}"
            )
        metadata = _parse_metadata(project.project_metadata)
        # Store the extended fields under a dedicated key.
        extended: dict[str, str] = {}
        for field in TopicField:
            value = self._draft.get(field.value, "")
            if value:
                extended[field.value] = value
        if extended:
            metadata[_METADATA_KEY] = extended
        else:
            metadata.pop(_METADATA_KEY, None)

        topic_value = self._draft.get(TopicField.BROAD_SUBJECT.value, "")
        changes: dict[str, Any] = {
            "topic": topic_value,
            "project_metadata": json.dumps(metadata, sort_keys=True)
            if metadata
            else None,
        }
        payload = ResearchProjectUpdate(**changes)
        try:
            repo.update(project, payload)
        except RepositoryError as exc:
            raise TopicWorkspaceError(
                f"Unable to persist the topic draft: {exc}"
            ) from exc
        self._record_audit(
            actor=actor,
            action=action,
            target_identifier=self._project_key,
            summary="Topic draft saved",
        )

    def _record_audit(
        self,
        *,
        actor: str,
        action: str,
        target_identifier: str,
        summary: str,
    ) -> None:
        try:
            session = self._repositories.get("audit_event").session
            session.add(
                AuditEvent(
                    actor=actor or "system",
                    action=action,
                    target_type="research_project",
                    target_identifier=target_identifier,
                    summary=summary,
                )
            )
            session.flush()
        except Exception as exc:  # noqa: BLE001 - boundary
            _logger.warning(
                "Unable to record the audit event for %s: %s",
                target_identifier,
                exc,
            )


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


def _compute_completeness(draft: dict[str, str]) -> TopicCompleteness:
    populated: list[TopicField] = []
    missing_essential: list[TopicField] = []
    for field in TopicField:
        if draft.get(field.value, "").strip():
            populated.append(field)
    for field in ESSENTIAL_FIELDS:
        if field not in populated:
            missing_essential.append(field)
    return TopicCompleteness(
        populated=tuple(populated),
        missing_essential=tuple(missing_essential),
        populated_count=len(populated),
        total_count=len(TopicField),
    )