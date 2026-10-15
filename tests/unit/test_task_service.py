"""Tests for the research task service."""

from __future__ import annotations

import datetime as dt

import pytest

from academic_platform.application.tasks.errors import (
    TaskNotFoundError,
    TaskValidationError,
)
from academic_platform.application.tasks.model import (
    TaskPriority,
    TaskStatus,
)
from academic_platform.application.tasks.service import TaskService
from academic_platform.infrastructure.database import Database
from academic_platform.infrastructure.database.base import Base
from academic_platform.infrastructure.database.models import (
    AuditEvent,
    ResearchProject,
)
from academic_platform.infrastructure.repositories.factory import (
    _REPOSITORY_REGISTRY,
)
from academic_platform.infrastructure.repositories.manager import (
    RepositoryManager,
)


@pytest.fixture()
def database() -> Database:
    db = Database.in_memory()
    Base.metadata.create_all(db.engine)
    yield db
    db.dispose()


def _seed_project(database: Database, key: str = "proj-1") -> None:
    with database.session() as session:
        session.add(ResearchProject(key=key, title="Study"))


def test_create_task(database: Database) -> None:
    _seed_project(database)
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = TaskService(repositories)
        view = service.create_task("proj-1", title="Read papers")
        assert view.title == "Read papers"
        assert view.status is TaskStatus.OPEN
        assert view.priority is TaskPriority.NORMAL
        assert view.is_milestone is False


def test_create_task_rejects_empty_title(database: Database) -> None:
    _seed_project(database)
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = TaskService(repositories)
        with pytest.raises(TaskValidationError):
            service.create_task("proj-1", title="   ")


def test_create_milestone(database: Database) -> None:
    _seed_project(database)
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = TaskService(repositories)
        view = service.create_task(
            "proj-1", title="Complete literature review", is_milestone=True
        )
        assert view.is_milestone is True


def test_set_status_to_done_records_completed_at(database: Database) -> None:
    _seed_project(database)
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = TaskService(repositories)
        task = service.create_task("proj-1", title="T")
        updated = service.set_status("proj-1", task.identifier, TaskStatus.DONE)
        assert updated.status is TaskStatus.DONE
        assert updated.completed_at is not None


def test_reopening_clears_completed_at(database: Database) -> None:
    _seed_project(database)
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = TaskService(repositories)
        task = service.create_task("proj-1", title="T")
        service.set_status("proj-1", task.identifier, TaskStatus.DONE)
        reopened = service.set_status("proj-1", task.identifier, TaskStatus.OPEN)
        assert reopened.completed_at is None


def test_set_priority(database: Database) -> None:
    _seed_project(database)
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = TaskService(repositories)
        task = service.create_task("proj-1", title="T")
        updated = service.set_priority(
            "proj-1", task.identifier, TaskPriority.HIGH
        )
        assert updated.priority is TaskPriority.HIGH


def test_mark_and_clear_milestone(database: Database) -> None:
    _seed_project(database)
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = TaskService(repositories)
        task = service.create_task("proj-1", title="T")
        marked = service.mark_milestone("proj-1", task.identifier)
        assert marked.is_milestone is True
        cleared = service.clear_milestone("proj-1", task.identifier)
        assert cleared.is_milestone is False


def test_due_date_parsed_from_string(database: Database) -> None:
    _seed_project(database)
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = TaskService(repositories)
        view = service.create_task(
            "proj-1", title="T", due_at="2024-06-01T12:00:00"
        )
        assert view.due_at is not None
        assert "2024-06-01" in view.due_at


def test_invalid_due_date_raises(database: Database) -> None:
    _seed_project(database)
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = TaskService(repositories)
        with pytest.raises(TaskValidationError):
            service.create_task("proj-1", title="T", due_at="not a date")


def test_clear_due_date(database: Database) -> None:
    _seed_project(database)
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = TaskService(repositories)
        task = service.create_task(
            "proj-1", title="T", due_at="2024-06-01T12:00:00"
        )
        cleared = service.update_task(
            "proj-1", task.identifier, clear_due_at=True
        )
        assert cleared.due_at is None


def test_progress_summary(database: Database) -> None:
    _seed_project(database)
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = TaskService(repositories)
        a = service.create_task("proj-1", title="A")
        b = service.create_task("proj-1", title="B", is_milestone=True)
        service.create_task("proj-1", title="C")
        service.set_status("proj-1", a.identifier, TaskStatus.DONE)
        summary = service.progress_summary("proj-1")
        assert summary.total == 3
        assert summary.done == 1
        assert summary.open == 2
        assert summary.milestones_total == 1
        assert summary.milestones_done == 0
        assert summary.completion_ratio == pytest.approx(1 / 3)


def test_overdue_detection(database: Database) -> None:
    _seed_project(database)
    past = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=1)
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = TaskService(repositories)
        service.create_task("proj-1", title="Overdue", due_at=past)
        service.create_task("proj-1", title="Not overdue")
        summary = service.progress_summary("proj-1")
        assert summary.overdue == 1


def test_list_tasks_by_status(database: Database) -> None:
    _seed_project(database)
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = TaskService(repositories)
        a = service.create_task("proj-1", title="A")
        service.create_task("proj-1", title="B")
        service.set_status("proj-1", a.identifier, TaskStatus.DONE)
        done = service.list_tasks_by_status("proj-1", TaskStatus.DONE)
        assert [t.title for t in done] == ["A"]


def test_delete_task(database: Database) -> None:
    _seed_project(database)
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = TaskService(repositories)
        task = service.create_task("proj-1", title="T")
        service.delete_task("proj-1", task.identifier)
        assert service.list_tasks("proj-1") == []


def test_reorder_tasks(database: Database) -> None:
    _seed_project(database)
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = TaskService(repositories)
        a = service.create_task("proj-1", title="A")
        b = service.create_task("proj-1", title="B")
        updated = service.reorder_tasks(
            "proj-1", [b.identifier, a.identifier]
        )
        assert updated == 2
        ordered = service.list_tasks("proj-1")
        assert [t.title for t in ordered] == ["B", "A"]


def test_audit_events_recorded(database: Database) -> None:
    _seed_project(database)
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = TaskService(repositories)
        task = service.create_task(
            "proj-1", title="T", is_milestone=True, actor="alice"
        )
        service.set_status(
            "proj-1", task.identifier, TaskStatus.DONE, actor="alice"
        )
        service.set_priority(
            "proj-1", task.identifier, TaskPriority.HIGH, actor="alice"
        )
        service.clear_milestone("proj-1", task.identifier, actor="alice")
        service.delete_task("proj-1", task.identifier, actor="alice")
    with database.session() as session:
        actions = {event.action for event in session.query(AuditEvent).all()}
        assert "task.created" in actions
        assert "task.milestone_set" in actions
        assert "task.status_changed" in actions
        assert "task.priority_changed" in actions
        assert "task.milestone_cleared" in actions
        assert "task.deleted" in actions


def test_unknown_project_raises(database: Database) -> None:
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = TaskService(repositories)
        with pytest.raises(TaskNotFoundError):
            service.create_task("missing", title="T")


def test_task_not_in_project_raises(database: Database) -> None:
    _seed_project(database, "a")
    _seed_project(database, "b")
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = TaskService(repositories)
        task = service.create_task("a", title="T")
        with pytest.raises(TaskNotFoundError):
            service.update_task("b", task.identifier, title="X")