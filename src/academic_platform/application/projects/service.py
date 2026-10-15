"""Application service for research projects.

The service is the single entry point the presentation layer uses to
manage research projects and their child entities. It:

- Creates, reads, updates, archives, deletes, and versions projects.
- Manages the project's research questions.
- Manages the project's tasks.
- Writes an audit event for every mutation.
- Updates the project-linked collection's title when the project's
  title changes, so that the collection view remains consistent.

Design decisions
----------------
- The service never commits. It runs inside a unit of work supplied by
  the caller.
- Validation is fail-closed. A validation failure raises
  ``ProjectValidationError`` with all issues at once; the caller never
  sees a partially applied mutation.
- The service is idempotent with respect to creation: creating a
  project whose key already exists raises ``ProjectValidationError``
  rather than silently updating the existing row. Updating an existing
  project is an explicit operation.
- Deleting a project removes the project's rows and the project's
  linked collection through the model's cascade. The service does not
  delete the linked documents themselves.
- Audit events record the actor, the action identifier, the target, and
  a short summary. They are append-only.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from academic_platform.application.projects.errors import (
    ProjectError,
    ProjectNotFoundError,
    ProjectValidationError,
)
from academic_platform.application.projects.model import (
    ProjectQuestionView,
    ProjectStage,
    ProjectTaskView,
    ProjectView,
)
from academic_platform.infrastructure.database.models import (
    AuditEvent,
    Collection,
    ResearchProject,
    ResearchQuestion,
    ResearchTask,
)
from academic_platform.infrastructure.database.schemas import (
    ResearchProjectCreate,
    ResearchProjectUpdate,
    ResearchQuestionCreate,
    ResearchQuestionUpdate,
    ResearchTaskCreate,
    ResearchTaskUpdate,
)
from academic_platform.infrastructure.repositories.errors import (
    DuplicateEntityError,
    RepositoryError,
)
from academic_platform.infrastructure.repositories.manager import (
    RepositoryManager,
)

_logger = logging.getLogger(__name__)

_PROJECT_COLLECTION_PREFIX = "project-"

_ACTION_PROJECT_CREATED = "project.created"
_ACTION_PROJECT_UPDATED = "project.updated"
_ACTION_PROJECT_STAGE_CHANGED = "project.stage_changed"
_ACTION_PROJECT_DELETED = "project.deleted"
_ACTION_QUESTION_ADDED = "project.question_added"
_ACTION_QUESTION_UPDATED = "project.question_updated"
_ACTION_QUESTION_REMOVED = "project.question_removed"
_ACTION_QUESTION_PRIMARY_CHANGED = "project.question_primary_changed"
_ACTION_TASK_ADDED = "project.task_added"
_ACTION_TASK_UPDATED = "project.task_updated"
_ACTION_TASK_COMPLETED = "project.task_completed"
_ACTION_TASK_REMOVED = "project.task_removed"


class ProjectService:
    """Application service for research projects."""

    def __init__(self, repositories: RepositoryManager) -> None:
        self._repositories = repositories

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------
    def list_projects(self, *, include_archived: bool = False) -> list[ProjectView]:
        """Return every project ordered by most recently updated first."""
        repo = self._repositories.get("research_project")
        try:
            rows = repo.list_ordered_by_updated()
        except RepositoryError as exc:
            raise ProjectError(f"Unable to list projects: {exc}") from exc
        if not include_archived:
            rows = [row for row in rows if row.stage != ProjectStage.ARCHIVED.value]
        return [self._to_view(row) for row in rows]

    def get_project(self, key: str) -> ProjectView:
        """Return the project with the given key."""
        return self._to_view(self._require_project(key))

    def list_questions(self, key: str) -> list[ProjectQuestionView]:
        """Return the project's research questions ordered by position."""
        project = self._require_project(key)
        repo = self._repositories.get("research_question")
        try:
            rows = repo.list_for_project(project.id)
        except RepositoryError as exc:
            raise ProjectError(f"Unable to list questions: {exc}") from exc
        return [self._to_question_view(row) for row in rows]

    def list_tasks(self, key: str) -> list[ProjectTaskView]:
        """Return the project's tasks ordered by position."""
        project = self._require_project(key)
        repo = self._repositories.get("research_task")
        try:
            rows = repo.list_for_project(project.id)
        except RepositoryError as exc:
            raise ProjectError(f"Unable to list tasks: {exc}") from exc
        return [self._to_task_view(row) for row in rows]

    def list_open_tasks(self, key: str) -> list[ProjectTaskView]:
        """Return the project's open tasks ordered by position."""
        project = self._require_project(key)
        repo = self._repositories.get("research_task")
        try:
            rows = repo.list_open_for_project(project.id)
        except RepositoryError as exc:
            raise ProjectError(f"Unable to list open tasks: {exc}") from exc
        return [self._to_task_view(row) for row in rows]

    # ------------------------------------------------------------------
    # Project writes
    # ------------------------------------------------------------------
    def create_project(
        self,
        *,
        key: str,
        title: str = "",
        topic: str = "",
        stage: ProjectStage = ProjectStage.IDEA,
        actor: str = "system",
    ) -> ProjectView:
        """Create a project and its linked collection."""
        issues = _validate_project_payload(key=key, title=title, topic=topic)
        if issues:
            raise ProjectValidationError(issues)
        repo = self._repositories.get("research_project")
        payload = ResearchProjectCreate(
            key=key,
            title=title,
            topic=topic,
            stage=stage.value,
        )
        try:
            row = repo.create(payload)
        except DuplicateEntityError as exc:
            raise ProjectValidationError(
                [f"A project with key {key!r} already exists"]
            ) from exc
        except RepositoryError as exc:
            raise ProjectError(f"Unable to create the project: {exc}") from exc
        self._ensure_project_collection(row)
        self._record_audit(
            actor=actor,
            action=_ACTION_PROJECT_CREATED,
            target_type="research_project",
            target_identifier=key,
            summary=f"Created project {row.title or key!r}",
        )
        return self._to_view(row)

    def update_project(
        self,
        key: str,
        *,
        title: str | None = None,
        topic: str | None = None,
        stage: ProjectStage | None = None,
        project_metadata: str | None = None,
        actor: str = "system",
    ) -> ProjectView:
        """Apply changes to an existing project."""
        project = self._require_project(key)
        issues = _validate_project_payload(
            key=key,
            title=title if title is not None else project.title,
            topic=topic if topic is not None else project.topic,
        )
        if issues:
            raise ProjectValidationError(issues)
        changes: dict[str, Any] = {}
        if title is not None:
            changes["title"] = title
        if topic is not None:
            changes["topic"] = topic
        if stage is not None:
            changes["stage"] = stage.value
        if project_metadata is not None:
            changes["project_metadata"] = project_metadata
        if not changes:
            return self._to_view(project)
        payload = ResearchProjectUpdate(**changes)
        repo = self._repositories.get("research_project")
        try:
            updated = repo.update(project, payload)
        except RepositoryError as exc:
            raise ProjectError(f"Unable to update the project: {exc}") from exc
        if title is not None:
            self._sync_project_collection_title(updated)
        if stage is not None and stage.value != project.stage:
            self._record_audit(
                actor=actor,
                action=_ACTION_PROJECT_STAGE_CHANGED,
                target_type="research_project",
                target_identifier=key,
                summary=f"Stage changed to {stage.display_name}",
            )
        self._record_audit(
            actor=actor,
            action=_ACTION_PROJECT_UPDATED,
            target_type="research_project",
            target_identifier=key,
            summary="Project updated",
            payload={"changed": sorted(changes.keys())},
        )
        return self._to_view(updated)

    def delete_project(self, key: str, *, actor: str = "system") -> None:
        """Delete a project and its children.

        The linked collection is removed through the model's cascade. The
        documents that were linked to the collection are not deleted.
        """
        project = self._require_project(key)
        repo = self._repositories.get("research_project")
        try:
            repo.delete(project)
        except RepositoryError as exc:
            raise ProjectError(f"Unable to delete the project: {exc}") from exc
        self._record_audit(
            actor=actor,
            action=_ACTION_PROJECT_DELETED,
            target_type="research_project",
            target_identifier=key,
            summary=f"Deleted project {project.title or key!r}",
        )

    # ------------------------------------------------------------------
    # Question writes
    # ------------------------------------------------------------------
    def add_question(
        self,
        key: str,
        *,
        text: str,
        kind: str = "main",
        is_primary: bool = False,
        actor: str = "system",
    ) -> ProjectQuestionView:
        """Add a research question to a project."""
        issues = _validate_question_payload(text=text, kind=kind)
        if issues:
            raise ProjectValidationError(issues)
        project = self._require_project(key)
        repo = self._repositories.get("research_question")
        try:
            position = repo.next_position(project.id)
        except RepositoryError:
            position = 0
        payload = ResearchQuestionCreate(
            project_id=project.id,
            text=text,
            kind=kind,
            is_primary=is_primary,
            position=position,
        )
        if is_primary:
            try:
                repo.clear_primary_for_project(project.id)
            except RepositoryError:
                pass
        try:
            row = repo.create(payload)
        except RepositoryError as exc:
            raise ProjectError(f"Unable to add the question: {exc}") from exc
        if is_primary:
            self._record_audit(
                actor=actor,
                action=_ACTION_QUESTION_PRIMARY_CHANGED,
                target_type="research_project",
                target_identifier=key,
                summary=f"Primary question set to {text[:80]!r}",
            )
        self._record_audit(
            actor=actor,
            action=_ACTION_QUESTION_ADDED,
            target_type="research_project",
            target_identifier=key,
            summary=f"Added question {text[:80]!r}",
        )
        return self._to_question_view(row)

    def update_question(
        self,
        project_key: str,
        question_id: int,
        *,
        text: str | None = None,
        kind: str | None = None,
        is_primary: bool | None = None,
        position: int | None = None,
        actor: str = "system",
    ) -> ProjectQuestionView:
        """Apply changes to a research question."""
        project = self._require_project(project_key)
        repo = self._repositories.get("research_question")
        try:
            row = repo.get(question_id)
        except RepositoryError as exc:
            raise ProjectError(f"Unable to read the question: {exc}") from exc
        if row is None or row.project_id != project.id:
            raise ProjectNotFoundError(
                f"No question with id {question_id!r} in project {project_key!r}"
            )
        if text is not None or kind is not None:
            issues = _validate_question_payload(
                text=text if text is not None else row.text,
                kind=kind if kind is not None else row.kind,
            )
            if issues:
                raise ProjectValidationError(issues)
        if is_primary:
            try:
                repo.clear_primary_for_project(project.id)
            except RepositoryError:
                pass
        changes: dict[str, Any] = {}
        if text is not None:
            changes["text"] = text
        if kind is not None:
            changes["kind"] = kind
        if is_primary is not None:
            changes["is_primary"] = is_primary
        if position is not None:
            changes["position"] = position
        if not changes:
            return self._to_question_view(row)
        payload = ResearchQuestionUpdate(**changes)
        try:
            updated = repo.update(row, payload)
        except RepositoryError as exc:
            raise ProjectError(f"Unable to update the question: {exc}") from exc
        if is_primary:
            self._record_audit(
                actor=actor,
                action=_ACTION_QUESTION_PRIMARY_CHANGED,
                target_type="research_project",
                target_identifier=project_key,
                summary=f"Primary question set to {updated.text[:80]!r}",
            )
        self._record_audit(
            actor=actor,
            action=_ACTION_QUESTION_UPDATED,
            target_type="research_project",
            target_identifier=project_key,
            summary=f"Updated question {updated.text[:80]!r}",
        )
        return self._to_question_view(updated)

    def remove_question(
        self,
        project_key: str,
        question_id: int,
        *,
        actor: str = "system",
    ) -> None:
        """Remove a research question from a project."""
        project = self._require_project(project_key)
        repo = self._repositories.get("research_question")
        try:
            row = repo.get(question_id)
        except RepositoryError as exc:
            raise ProjectError(f"Unable to read the question: {exc}") from exc
        if row is None or row.project_id != project.id:
            raise ProjectNotFoundError(
                f"No question with id {question_id!r} in project {project_key!r}"
            )
        try:
            repo.delete(row)
        except RepositoryError as exc:
            raise ProjectError(f"Unable to remove the question: {exc}") from exc
        self._record_audit(
            actor=actor,
            action=_ACTION_QUESTION_REMOVED,
            target_type="research_project",
            target_identifier=project_key,
            summary=f"Removed question {row.text[:80]!r}",
        )

    def set_primary_question(
        self,
        project_key: str,
        question_id: int,
        *,
        actor: str = "system",
    ) -> ProjectQuestionView:
        """Designate a research question as the project's primary question."""
        return self.update_question(
            project_key,
            question_id,
            is_primary=True,
            actor=actor,
        )

    # ------------------------------------------------------------------
    # Task writes
    # ------------------------------------------------------------------
    def add_task(
        self,
        key: str,
        *,
        title: str,
        description: str = "",
        actor: str = "system",
    ) -> ProjectTaskView:
        """Add a task to a project."""
        issues = _validate_task_payload(title=title)
        if issues:
            raise ProjectValidationError(issues)
        project = self._require_project(key)
        repo = self._repositories.get("research_task")
        try:
            existing = repo.list_for_project(project.id)
            position = len(existing)
        except RepositoryError:
            position = 0
        payload = ResearchTaskCreate(
            project_id=project.id,
            title=title,
            description=description,
            position=position,
        )
        try:
            row = repo.create(payload)
        except RepositoryError as exc:
            raise ProjectError(f"Unable to add the task: {exc}") from exc
        self._record_audit(
            actor=actor,
            action=_ACTION_TASK_ADDED,
            target_type="research_project",
            target_identifier=key,
            summary=f"Added task {title[:80]!r}",
        )
        return self._to_task_view(row)

    def update_task(
        self,
        project_key: str,
        task_id: int,
        *,
        title: str | None = None,
        description: str | None = None,
        completed: bool | None = None,
        position: int | None = None,
        actor: str = "system",
    ) -> ProjectTaskView:
        """Apply changes to a research task."""
        project = self._require_project(project_key)
        repo = self._repositories.get("research_task")
        try:
            row = repo.get(task_id)
        except RepositoryError as exc:
            raise ProjectError(f"Unable to read the task: {exc}") from exc
        if row is None or row.project_id != project.id:
            raise ProjectNotFoundError(
                f"No task with id {task_id!r} in project {project_key!r}"
            )
        if title is not None:
            issues = _validate_task_payload(title=title)
            if issues:
                raise ProjectValidationError(issues)
        changes: dict[str, Any] = {}
        if title is not None:
            changes["title"] = title
        if description is not None:
            changes["description"] = description
        if completed is not None:
            changes["completed"] = completed
        if position is not None:
            changes["position"] = position
        if not changes:
            return self._to_task_view(row)
        payload = ResearchTaskUpdate(**changes)
        try:
            updated = repo.update(row, payload)
        except RepositoryError as exc:
            raise ProjectError(f"Unable to update the task: {exc}") from exc
        if completed is not None:
            self._record_audit(
                actor=actor,
                action=_ACTION_TASK_COMPLETED,
                target_type="research_project",
                target_identifier=project_key,
                summary=(
                    f"Completed task {updated.title[:80]!r}"
                    if completed
                    else f"Reopened task {updated.title[:80]!r}"
                ),
            )
        else:
            self._record_audit(
                actor=actor,
                action=_ACTION_TASK_UPDATED,
                target_type="research_project",
                target_identifier=project_key,
                summary=f"Updated task {updated.title[:80]!r}",
            )
        return self._to_task_view(updated)

    def remove_task(
        self,
        project_key: str,
        task_id: int,
        *,
        actor: str = "system",
    ) -> None:
        """Remove a task from a project."""
        project = self._require_project(project_key)
        repo = self._repositories.get("research_task")
        try:
            row = repo.get(task_id)
        except RepositoryError as exc:
            raise ProjectError(f"Unable to read the task: {exc}") from exc
        if row is None or row.project_id != project.id:
            raise ProjectNotFoundError(
                f"No task with id {task_id!r} in project {project_key!r}"
            )
        try:
            repo.delete(row)
        except RepositoryError as exc:
            raise ProjectError(f"Unable to remove the task: {exc}") from exc
        self._record_audit(
            actor=actor,
            action=_ACTION_TASK_REMOVED,
            target_type="research_project",
            target_identifier=project_key,
            summary=f"Removed task {row.title[:80]!r}",
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _require_project(self, key: str) -> ResearchProject:
        repo = self._repositories.get("research_project")
        try:
            row = repo.find_by_key(key)
        except RepositoryError as exc:
            raise ProjectError(f"Unable to read the project: {exc}") from exc
        if row is None:
            raise ProjectNotFoundError(f"No project with key {key!r}")
        return row

    def _ensure_project_collection(self, project: ResearchProject) -> None:
        repo = self._repositories.get("collection")
        collection_key = f"{_PROJECT_COLLECTION_PREFIX}{project.key}"
        try:
            existing = repo.find_by_key(collection_key)
        except RepositoryError:
            existing = None
        if existing is not None:
            return
        collection = Collection(
            key=collection_key,
            title=f"{project.title or project.key} — documents",
            description=(
                "Documents associated with the project. Managed "
                "automatically when documents are linked to the project."
            ),
            kind="project",
            project_id=project.id,
        )
        try:
            repo.add(collection)
        except DuplicateEntityError:
            # A concurrent operation created it; no action required.
            return
        except RepositoryError as exc:
            _logger.warning(
                "Unable to create the project collection for %s: %s",
                project.key,
                exc,
            )

    def _sync_project_collection_title(self, project: ResearchProject) -> None:
        repo = self._repositories.get("collection")
        collection_key = f"{_PROJECT_COLLECTION_PREFIX}{project.key}"
        try:
            collection = repo.find_by_key(collection_key)
        except RepositoryError:
            collection = None
        if collection is None:
            return
        collection.title = f"{project.title or project.key} — documents"
        try:
            repo.session.flush()
        except RepositoryError:
            _logger.warning(
                "Unable to update the collection title for %s", project.key
            )

    def _to_view(self, project: ResearchProject) -> ProjectView:
        question_repo = self._repositories.get("research_question")
        task_repo = self._repositories.get("research_task")
        collection_repo = self._repositories.get("collection")
        item_repo = self._repositories.get("collection_item")

        questions: list[ProjectQuestionView] = []
        try:
            questions = [
                self._to_question_view(row)
                for row in question_repo.list_for_project(project.id)
            ]
        except RepositoryError:
            questions = []

        try:
            tasks = task_repo.list_for_project(project.id)
            total_tasks = len(tasks)
            open_tasks = sum(1 for task in tasks if not task.completed)
        except RepositoryError:
            total_tasks = 0
            open_tasks = 0

        document_count = 0
        try:
            collection = collection_repo.find_by_key(
                f"{_PROJECT_COLLECTION_PREFIX}{project.key}"
            )
            if collection is not None:
                document_count = len(item_repo.list_for_collection(collection.id))
        except RepositoryError:
            document_count = 0

        return ProjectView(
            identifier=project.id,
            key=project.key,
            title=project.title,
            topic=project.topic,
            stage=_project_stage(project.stage),
            created_at=project.created_at.isoformat() if project.created_at else "",
            updated_at=project.updated_at.isoformat() if project.updated_at else "",
            version=project.version or 1,
            question_count=len(questions),
            open_task_count=open_tasks,
            total_task_count=total_tasks,
            document_count=document_count,
            questions=tuple(questions),
        )

    def _to_question_view(self, row: ResearchQuestion) -> ProjectQuestionView:
        return ProjectQuestionView(
            identifier=row.id,
            text=row.text,
            kind=row.kind,
            is_primary=bool(row.is_primary),
            position=row.position,
            created_at=row.created_at.isoformat() if row.created_at else "",
            updated_at=row.updated_at.isoformat() if row.updated_at else "",
        )

    def _to_task_view(self, row: ResearchTask) -> ProjectTaskView:
        return ProjectTaskView(
            identifier=row.id,
            title=row.title,
            description=row.description,
            completed=bool(row.completed),
            position=row.position,
            due_at=row.due_at.isoformat() if row.due_at else None,
            created_at=row.created_at.isoformat() if row.created_at else "",
            updated_at=row.updated_at.isoformat() if row.updated_at else "",
        )

    def _record_audit(
        self,
        *,
        actor: str,
        action: str,
        target_type: str,
        target_identifier: str,
        summary: str,
        payload: dict[str, Any] | None = None,
    ) -> None:
        try:
            session = self._repositories.get("audit_event").session
            session.add(
                AuditEvent(
                    actor=actor or "system",
                    action=action,
                    target_type=target_type,
                    target_identifier=target_identifier,
                    summary=summary,
                    payload_json=json.dumps(payload) if payload else None,
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
# Validation helpers
# ----------------------------------------------------------------------
def _validate_project_payload(*, key: str, title: str, topic: str) -> list[str]:
    issues: list[str] = []
    cleaned_key = (key or "").strip()
    if not cleaned_key:
        issues.append("Project key must not be empty")
    else:
        if not cleaned_key[0].isalnum():
            issues.append("Project key must start with a letter or digit")
        for character in cleaned_key:
            if not (character.isalnum() or character in "-_"):
                issues.append(
                    "Project key may contain letters, digits, hyphens, and "
                    "underscores"
                )
                break
        if cleaned_key != cleaned_key.lower():
            issues.append("Project key must be lowercase")
    if title and len(title) > 512:
        issues.append("Project title must be at most 512 characters")
    if topic and len(topic) > 1024:
        issues.append("Project topic must be at most 1024 characters")
    return issues


def _validate_question_payload(*, text: str, kind: str) -> list[str]:
    issues: list[str] = []
    if not text or not text.strip():
        issues.append("Question text must not be empty")
    elif len(text) > 2048:
        issues.append("Question text must be at most 2048 characters")
    if kind not in {"main", "sub", "exploratory", "hypothesis"}:
        issues.append(
            "Question kind must be one of: main, sub, exploratory, hypothesis"
        )
    return issues


def _validate_task_payload(*, title: str) -> list[str]:
    issues: list[str] = []
    if not title or not title.strip():
        issues.append("Task title must not be empty")
    elif len(title) > 512:
        issues.append("Task title must be at most 512 characters")
    return issues


def _project_stage(value: str) -> ProjectStage:
    try:
        return ProjectStage(value)
    except ValueError:
        return ProjectStage.IDEA