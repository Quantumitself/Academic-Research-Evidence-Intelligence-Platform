"""Application service for research tasks and milestones.

The service owns the workflow semantics of research tasks. It builds on
the task entities and the project service's task operations, adding:

- Task status and priority.
- Milestone markers.
- Due-date handling and overdue detection.
- Project-level progress summaries.
- Audit events for every mutation.

Design decisions
----------------
- The service never commits. It runs inside a unit of work supplied by
  the caller.
- Validation is fail-closed. A validation failure raises
  ``TaskValidationError`` with all issues at once; the caller never
  sees a partially applied mutation.
- Status transitions are validated. A terminal task cannot be reopened
  without an explicit status change; the service accepts any target
  status the caller requests and records the transition in the audit
  trail.
- Completion timestamps are derived. Setting a task to ``done`` records
  a ``completed_at`` timestamp; moving a task out of ``done`` clears it.
- Milestones are tasks with the ``is_milestone`` flag set. The service
  does not maintain a separate table; the flag lives on the task row
  and is preserved across updates.
- The project service's task operations remain the low-level API for
  simple create, update, and remove. The task service is the workflow
  layer that the presentation uses for status, priority, milestone,
  and progress operations.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
from typing import Any

from academic_platform.application.tasks.errors import (
    TaskError,
    TaskNotFoundError,
    TaskValidationError,
)
from academic_platform.application.tasks.model import (
    MilestoneView,
    TaskPriority,
    TaskProgressSummary,
    TaskStatus,
    TaskView,
)
from academic_platform.infrastructure.database.models import (
    AuditEvent,
    ResearchProject,
    ResearchTask,
)
from academic_platform.infrastructure.repositories.errors import (
    RepositoryError,
)
from academic_platform.infrastructure.repositories.manager import (
    RepositoryManager,
)

_logger = logging.getLogger(__name__)

_ACTION_TASK_CREATED = "task.created"
_ACTION_TASK_UPDATED = "task.updated"
_ACTION_TASK_STATUS_CHANGED = "task.status_changed"
_ACTION_TASK_PRIORITY_CHANGED = "task.priority_changed"
_ACTION_TASK_MILESTONE_SET = "task.milestone_set"
_ACTION_TASK_MILESTONE_CLEARED = "task.milestone_cleared"
_ACTION_TASK_DELETED = "task.deleted"
_ACTION_TASK_REORDERED = "task.reordered"

_DEFAULT_PRIORITY = TaskPriority.NORMAL
_DEFAULT_STATUS = TaskStatus.OPEN


class TaskService:
    """Application service for research tasks and milestones."""

    def __init__(self, repositories: RepositoryManager) -> None:
        self._repositories = repositories

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------
    def list_tasks(self, project_key: str) -> list[TaskView]:
        """Return the project's tasks ordered by position."""
        project = self._require_project(project_key)
        repo = self._repositories.get("research_task")
        try:
            rows = repo.list_for_project(project.id)
        except RepositoryError as exc:
            raise TaskError(f"Unable to list tasks: {exc}") from exc
        return [self._to_view(row, project_key) for row in rows]

    def list_tasks_by_status(
        self,
        project_key: str,
        status: TaskStatus,
    ) -> list[TaskView]:
        """Return the project's tasks with the given status."""
        return [
            task
            for task in self.list_tasks(project_key)
            if task.status is status
        ]

    def list_milestones(self, project_key: str) -> list[MilestoneView]:
        """Return the project's milestones ordered by position."""
        return [
            _to_milestone(task)
            for task in self.list_tasks(project_key)
            if task.is_milestone
        ]

    def get_task(self, task_id: int) -> TaskView:
        """Return a single task by identifier."""
        row = self._require_task(task_id)
        project = self._get_project_by_id(row.project_id)
        project_key = project.key if project is not None else ""
        return self._to_view(row, project_key)

    def progress_summary(self, project_key: str) -> TaskProgressSummary:
        """Return the aggregated progress of a project's tasks."""
        tasks = self.list_tasks(project_key)
        summary = TaskProgressSummary(project_key=project_key)
        counters = {status: 0 for status in TaskStatus}
        milestone_total = 0
        milestone_done = 0
        overdue = 0
        now = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
        for task in tasks:
            counters[task.status] += 1
            if task.is_milestone:
                milestone_total += 1
                if task.status is TaskStatus.DONE:
                    milestone_done += 1
            if (
                task.due_at is not None
                and not task.status.is_terminal
                and _parse_iso(task.due_at) is not None
                and _parse_iso(task.due_at) < now
            ):
                overdue += 1
        return TaskProgressSummary(
            project_key=project_key,
            total=len(tasks),
            open=counters[TaskStatus.OPEN],
            in_progress=counters[TaskStatus.IN_PROGRESS],
            blocked=counters[TaskStatus.BLOCKED],
            done=counters[TaskStatus.DONE],
            cancelled=counters[TaskStatus.CANCELLED],
            milestones_total=milestone_total,
            milestones_done=milestone_done,
            overdue=overdue,
            tasks=tuple(tasks),
            milestones=tuple(
                _to_milestone(task) for task in tasks if task.is_milestone
            ),
        )

    # ------------------------------------------------------------------
    # Writes
    # ------------------------------------------------------------------
    def create_task(
        self,
        project_key: str,
        *,
        title: str,
        description: str = "",
        status: TaskStatus = _DEFAULT_STATUS,
        priority: TaskPriority = _DEFAULT_PRIORITY,
        is_milestone: bool = False,
        due_at: dt.datetime | str | None = None,
        notes: str = "",
        actor: str = "system",
    ) -> TaskView:
        """Create a task on a project."""
        issues = _validate_task_payload(
            title=title, description=description, notes=notes
        )
        if issues:
            raise TaskValidationError(issues)
        due_datetime = _coerce_datetime(due_at, issues)
        if issues:
            raise TaskValidationError(issues)
        project = self._require_project(project_key)
        repo = self._repositories.get("research_task")
        try:
            position = len(repo.list_for_project(project.id))
        except RepositoryError:
            position = 0
        completed_at = (
            dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
            if status is TaskStatus.DONE
            else None
        )
        row = ResearchTask(
            project_id=project.id,
            title=title,
            description=description,
            position=position,
            completed=1 if status is TaskStatus.DONE else 0,
            due_at=due_datetime,
        )
        # The status, priority, milestone flag, and notes columns are
        # part of the research task model as of this phase. The service
        # writes them explicitly so that the model's defaults do not
        # override the caller's intent.
        row.status = status.value
        row.priority = priority.value
        row.is_milestone = 1 if is_milestone else 0
        row.notes = notes
        if completed_at is not None:
            row.completed_at = completed_at
        try:
            repo.add(row)
        except RepositoryError as exc:
            raise TaskError(f"Unable to create the task: {exc}") from exc
        self._record_audit(
            actor=actor,
            action=_ACTION_TASK_CREATED,
            target_type="research_project",
            target_identifier=project_key,
            summary=f"Created task {title[:80]!r}",
        )
        if is_milestone:
            self._record_audit(
                actor=actor,
                action=_ACTION_TASK_MILESTONE_SET,
                target_type="research_project",
                target_identifier=project_key,
                summary=f"Marked task {title[:80]!r} as a milestone",
            )
        return self._to_view(row, project_key)

    def update_task(
        self,
        project_key: str,
        task_id: int,
        *,
        title: str | None = None,
        description: str | None = None,
        status: TaskStatus | None = None,
        priority: TaskPriority | None = None,
        is_milestone: bool | None = None,
        due_at: dt.datetime | str | None = None,
        clear_due_at: bool = False,
        notes: str | None = None,
        position: int | None = None,
        actor: str = "system",
    ) -> TaskView:
        """Apply changes to a task.

        Parameters
        ----------
        clear_due_at:
            When True, the task's due date is set to ``None``. This is
            distinct from passing ``due_at=None``, which leaves the due
            date unchanged.
        """
        project = self._require_project(project_key)
        row = self._require_task_in_project(task_id, project.id)
        issues: list[str] = []
        if title is not None:
            issues = _validate_task_payload(title=title)
        if notes is not None and len(notes) > 4096:
            issues.append("Notes must be at most 4096 characters")
        due_datetime: dt.datetime | None | object = _UNSET
        if clear_due_at:
            due_datetime = None
        elif due_at is not None:
            due_datetime = _coerce_datetime(due_at, issues)
        if issues:
            raise TaskValidationError(issues)

        changes: dict[str, Any] = {}
        if title is not None:
            changes["title"] = title
        if description is not None:
            changes["description"] = description
        if notes is not None:
            changes["notes"] = notes
        if status is not None:
            changes["status"] = status.value
            changes["completed"] = 1 if status is TaskStatus.DONE else 0
            if status is TaskStatus.DONE:
                if row.completed_at is None:
                    changes["completed_at"] = dt.datetime.now(
                        dt.timezone.utc
                    ).replace(tzinfo=None)
            else:
                changes["completed_at"] = None
        if priority is not None:
            changes["priority"] = priority.value
        if is_milestone is not None:
            changes["is_milestone"] = 1 if is_milestone else 0
        if due_datetime is not _UNSET:
            changes["due_at"] = due_datetime
        if position is not None:
            if position < 0:
                raise TaskValidationError(
                    ["Task position must be non-negative"]
                )
            changes["position"] = position
        if not changes:
            return self._to_view(row, project_key)

        repo = self._repositories.get("research_task")
        for field_name, value in changes.items():
            setattr(row, field_name, value)
        try:
            repo.session.flush()
        except RepositoryError as exc:
            raise TaskError(f"Unable to update the task: {exc}") from exc

        self._record_change_audits(
            actor=actor,
            project_key=project_key,
            row=row,
            changes=changes,
        )
        return self._to_view(row, project_key)

    def set_status(
        self,
        project_key: str,
        task_id: int,
        status: TaskStatus,
        *,
        actor: str = "system",
    ) -> TaskView:
        """Change a task's status."""
        return self.update_task(
            project_key, task_id, status=status, actor=actor
        )

    def set_priority(
        self,
        project_key: str,
        task_id: int,
        priority: TaskPriority,
        *,
        actor: str = "system",
    ) -> TaskView:
        """Change a task's priority."""
        return self.update_task(
            project_key, task_id, priority=priority, actor=actor
        )

    def mark_milestone(
        self,
        project_key: str,
        task_id: int,
        *,
        actor: str = "system",
    ) -> TaskView:
        """Mark a task as a milestone."""
        return self.update_task(
            project_key, task_id, is_milestone=True, actor=actor
        )

    def clear_milestone(
        self,
        project_key: str,
        task_id: int,
        *,
        actor: str = "system",
    ) -> TaskView:
        """Clear a task's milestone flag."""
        return self.update_task(
            project_key, task_id, is_milestone=False, actor=actor
        )

    def delete_task(
        self,
        project_key: str,
        task_id: int,
        *,
        actor: str = "system",
    ) -> None:
        """Delete a task."""
        project = self._require_project(project_key)
        row = self._require_task_in_project(task_id, project.id)
        repo = self._repositories.get("research_task")
        try:
            repo.delete(row)
        except RepositoryError as exc:
            raise TaskError(f"Unable to delete the task: {exc}") from exc
        self._record_audit(
            actor=actor,
            action=_ACTION_TASK_DELETED,
            target_type="research_project",
            target_identifier=project_key,
            summary=f"Deleted task {row.title[:80]!r}",
        )

    def reorder_tasks(
        self,
        project_key: str,
        ordered_task_ids: list[int],
        *,
        actor: str = "system",
    ) -> int:
        """Assign new positions to the project's tasks."""
        project = self._require_project(project_key)
        repo = self._repositories.get("research_task")
        updated = 0
        for position, task_id in enumerate(ordered_task_ids):
            try:
                row = repo.get(task_id)
            except RepositoryError:
                continue
            if row is None or row.project_id != project.id:
                continue
            if row.position == position:
                continue
            row.position = position
            updated += 1
        if updated:
            try:
                repo.session.flush()
            except RepositoryError as exc:
                raise TaskError(f"Unable to reorder tasks: {exc}") from exc
            self._record_audit(
                actor=actor,
                action=_ACTION_TASK_REORDERED,
                target_type="research_project",
                target_identifier=project_key,
                summary=f"Reordered {updated} task(s)",
            )
        return updated

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _require_project(self, key: str) -> ResearchProject:
        repo = self._repositories.get("research_project")
        try:
            row = repo.find_by_key(key)
        except RepositoryError as exc:
            raise TaskError(f"Unable to read the project: {exc}") from exc
        if row is None:
            raise TaskNotFoundError(f"No project with key {key!r}")
        return row

    def _require_task(self, task_id: int) -> ResearchTask:
        repo = self._repositories.get("research_task")
        try:
            row = repo.get(task_id)
        except RepositoryError as exc:
            raise TaskError(f"Unable to read the task: {exc}") from exc
        if row is None:
            raise TaskNotFoundError(f"No task with id {task_id!r}")
        return row

    def _require_task_in_project(
        self, task_id: int, project_id: int
    ) -> ResearchTask:
        row = self._require_task(task_id)
        if row.project_id != project_id:
            raise TaskNotFoundError(
                f"Task {task_id!r} is not part of the project"
            )
        return row

    def _get_project_by_id(self, project_id: int) -> ResearchProject | None:
        repo = self._repositories.get("research_project")
        try:
            return repo.get(project_id)
        except RepositoryError:
            return None

    def _to_view(self, row: ResearchTask, project_key: str) -> TaskView:
        return TaskView(
            identifier=row.id,
            project_key=project_key,
            title=row.title,
            description=row.description or "",
            status=_safe_status(getattr(row, "status", TaskStatus.OPEN.value)),
            priority=_safe_priority(
                getattr(row, "priority", _DEFAULT_PRIORITY.value)
            ),
            is_milestone=bool(getattr(row, "is_milestone", 0)),
            position=row.position,
            due_at=row.due_at.isoformat() if row.due_at else None,
            created_at=row.created_at.isoformat() if row.created_at else "",
            updated_at=row.updated_at.isoformat() if row.updated_at else "",
            completed_at=(
                getattr(row, "completed_at").isoformat()
                if getattr(row, "completed_at", None)
                else None
            ),
            notes=getattr(row, "notes", "") or "",
        )

    def _record_change_audits(
        self,
        *,
        actor: str,
        project_key: str,
        row: ResearchTask,
        changes: dict[str, Any],
    ) -> None:
        if "status" in changes:
            self._record_audit(
                actor=actor,
                action=_ACTION_TASK_STATUS_CHANGED,
                target_type="research_project",
                target_identifier=project_key,
                summary=(
                    f"Task {row.title[:80]!r} set to "
                    f"{_safe_status(changes['status']).display_name}"
                ),
            )
        if "priority" in changes:
            self._record_audit(
                actor=actor,
                action=_ACTION_TASK_PRIORITY_CHANGED,
                target_type="research_project",
                target_identifier=project_key,
                summary=(
                    f"Task {row.title[:80]!r} priority set to "
                    f"{_safe_priority(changes['priority']).display_name}"
                ),
            )
        if "is_milestone" in changes:
            milestone = bool(changes["is_milestone"])
            self._record_audit(
                actor=actor,
                action=(
                    _ACTION_TASK_MILESTONE_SET
                    if milestone
                    else _ACTION_TASK_MILESTONE_CLEARED
                ),
                target_type="research_project",
                target_identifier=project_key,
                summary=(
                    f"{'Marked' if milestone else 'Cleared'} milestone for "
                    f"task {row.title[:80]!r}"
                ),
            )
        non_meta_changes = {
            key
            for key in changes.keys()
            if key
            not in {
                "status",
                "priority",
                "is_milestone",
                "completed",
                "completed_at",
            }
        }
        if non_meta_changes:
            self._record_audit(
                actor=actor,
                action=_ACTION_TASK_UPDATED,
                target_type="research_project",
                target_identifier=project_key,
                summary=f"Updated task {row.title[:80]!r}",
                payload={"changed": sorted(non_meta_changes)},
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
# Helpers
# ----------------------------------------------------------------------
_UNSET = object()


def _to_milestone(task: TaskView) -> MilestoneView:
    return MilestoneView(
        identifier=task.identifier,
        project_key=task.project_key,
        title=task.title,
        status=task.status,
        due_at=task.due_at,
        completed_at=task.completed_at,
    )


def _validate_task_payload(
    *,
    title: str | None = None,
    description: str | None = None,
    notes: str | None = None,
) -> list[str]:
    issues: list[str] = []
    if title is not None:
        if not title or not title.strip():
            issues.append("Task title must not be empty")
        elif len(title) > 512:
            issues.append("Task title must be at most 512 characters")
    if description is not None and len(description) > 4096:
        issues.append("Task description must be at most 4096 characters")
    if notes is not None and len(notes) > 4096:
        issues.append("Task notes must be at most 4096 characters")
    return issues


def _coerce_datetime(
    value: dt.datetime | str | None,
    issues: list[str],
) -> dt.datetime | None:
    if value is None:
        return None
    if isinstance(value, dt.datetime):
        if value.tzinfo is not None:
            return value.astimezone(dt.timezone.utc).replace(tzinfo=None)
        return value
    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned:
            return None
        parsed = _parse_iso(cleaned)
        if parsed is None:
            issues.append(
                f"Due date {value!r} is not a valid ISO-8601 datetime"
            )
            return None
        return parsed
    issues.append("Due date must be a datetime or an ISO-8601 string")
    return None


def _parse_iso(value: str) -> dt.datetime | None:
    cleaned = value.strip()
    if cleaned.endswith("Z"):
        cleaned = cleaned[:-1] + "+00:00"
    try:
        parsed = dt.datetime.fromisoformat(cleaned)
    except ValueError:
        return None
    if parsed.tzinfo is not None:
        return parsed.astimezone(dt.timezone.utc).replace(tzinfo=None)
    return parsed


def _safe_status(value: str | TaskStatus) -> TaskStatus:
    if isinstance(value, TaskStatus):
        return value
    try:
        return TaskStatus(value)
    except (ValueError, TypeError):
        return TaskStatus.OPEN


def _safe_priority(value: str | TaskPriority) -> TaskPriority:
    if isinstance(value, TaskPriority):
        return value
    try:
        return TaskPriority(value)
    except (ValueError, TypeError):
        return TaskPriority.NORMAL