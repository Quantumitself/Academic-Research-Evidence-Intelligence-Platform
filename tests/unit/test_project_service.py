"""Tests for the research project service."""

from __future__ import annotations

import pytest

from academic_platform.application.projects.errors import (
    ProjectNotFoundError,
    ProjectValidationError,
)
from academic_platform.application.projects.model import ProjectStage
from academic_platform.application.projects.service import ProjectService
from academic_platform.infrastructure.database import Database
from academic_platform.infrastructure.database.base import Base
from academic_platform.infrastructure.database.models import (
    AuditEvent,
    Collection,
    ResearchProject,
    ResearchQuestion,
    ResearchTask,
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


def _service(database: Database) -> ProjectService:
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        yield ProjectService(repositories)


def test_create_project(database: Database) -> None:
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = ProjectService(repositories)
        view = service.create_project(
            key="study-1", title="Study One", topic="Measurement"
        )
        assert view.key == "study-1"
        assert view.stage is ProjectStage.IDEA
        assert view.title == "Study One"


def test_create_project_creates_collection(database: Database) -> None:
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        ProjectService(repositories).create_project(key="study-1", title="S")
    with database.session() as session:
        collections = session.query(Collection).all()
        assert len(collections) == 1
        assert collections[0].key == "project-study-1"
        assert collections[0].kind == "project"


def test_create_project_rejects_duplicate(database: Database) -> None:
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = ProjectService(repositories)
        service.create_project(key="study-1")
    with pytest.raises(ProjectValidationError):
        with database.session() as session:
            repositories = RepositoryManager(session)
            repositories.register_all(dict(_REPOSITORY_REGISTRY))
            service = ProjectService(repositories)
            service.create_project(key="study-1")


def test_create_project_rejects_invalid_key(database: Database) -> None:
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = ProjectService(repositories)
        with pytest.raises(ProjectValidationError):
            service.create_project(key="Study 1")


def test_update_project(database: Database) -> None:
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = ProjectService(repositories)
        service.create_project(key="study-1", title="Old")
        view = service.update_project(
            "study-1", title="New", stage=ProjectStage.DESIGN
        )
        assert view.title == "New"
        assert view.stage is ProjectStage.DESIGN


def test_update_project_syncs_collection_title(database: Database) -> None:
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = ProjectService(repositories)
        service.create_project(key="study-1", title="Old")
        service.update_project("study-1", title="New")
    with database.session() as session:
        collection = session.query(Collection).one()
        assert "New" in collection.title


def test_update_project_missing_raises(database: Database) -> None:
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = ProjectService(repositories)
        with pytest.raises(ProjectNotFoundError):
            service.update_project("missing", title="X")


def test_delete_project(database: Database) -> None:
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = ProjectService(repositories)
        service.create_project(key="study-1")
        service.delete_project("study-1")
    with database.session() as session:
        assert session.query(ResearchProject).count() == 0
        assert session.query(Collection).count() == 0


def test_add_and_list_questions(database: Database) -> None:
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = ProjectService(repositories)
        service.create_project(key="study-1")
        service.add_question("study-1", text="First question?")
        service.add_question("study-1", text="Second question?")
        questions = service.list_questions("study-1")
        assert [q.text for q in questions] == ["First question?", "Second question?"]


def test_add_question_rejects_empty(database: Database) -> None:
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = ProjectService(repositories)
        service.create_project(key="study-1")
        with pytest.raises(ProjectValidationError):
            service.add_question("study-1", text="   ")


def test_set_primary_question(database: Database) -> None:
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = ProjectService(repositories)
        service.create_project(key="study-1")
        first = service.add_question("study-1", text="A")
        second = service.add_question("study-1", text="B")
        service.set_primary_question("study-1", first.identifier)
        service.set_primary_question("study-1", second.identifier)
        questions = service.list_questions("study-1")
        primary = [q for q in questions if q.is_primary]
        assert len(primary) == 1
        assert primary[0].text == "B"


def test_update_question(database: Database) -> None:
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = ProjectService(repositories)
        service.create_project(key="study-1")
        question = service.add_question("study-1", text="Old")
        updated = service.update_question(
            "study-1", question.identifier, text="New"
        )
        assert updated.text == "New"


def test_remove_question(database: Database) -> None:
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = ProjectService(repositories)
        service.create_project(key="study-1")
        question = service.add_question("study-1", text="A")
        service.remove_question("study-1", question.identifier)
    with database.session() as session:
        assert session.query(ResearchQuestion).count() == 0


def test_add_and_list_tasks(database: Database) -> None:
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = ProjectService(repositories)
        service.create_project(key="study-1")
        service.add_task("study-1", title="Read papers")
        service.add_task("study-1", title="Draft question")
        tasks = service.list_tasks("study-1")
        assert [t.title for t in tasks] == ["Read papers", "Draft question"]


def test_update_task_completion(database: Database) -> None:
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = ProjectService(repositories)
        service.create_project(key="study-1")
        task = service.add_task("study-1", title="Read")
        updated = service.update_task(
            "study-1", task.identifier, completed=True
        )
        assert updated.completed is True


def test_list_open_tasks(database: Database) -> None:
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = ProjectService(repositories)
        service.create_project(key="study-1")
        a = service.add_task("study-1", title="A")
        service.add_task("study-1", title="B")
        service.update_task("study-1", a.identifier, completed=True)
        open_tasks = service.list_open_tasks("study-1")
        assert [t.title for t in open_tasks] == ["B"]


def test_remove_task(database: Database) -> None:
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = ProjectService(repositories)
        service.create_project(key="study-1")
        task = service.add_task("study-1", title="A")
        service.remove_task("study-1", task.identifier)
    with database.session() as session:
        assert session.query(ResearchTask).count() == 0


def test_audit_events_recorded(database: Database) -> None:
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = ProjectService(repositories)
        service.create_project(key="study-1", actor="alice")
        service.add_question("study-1", text="Q", actor="alice")
        service.add_task("study-1", title="T", actor="alice")
        service.delete_project("study-1", actor="alice")
    with database.session() as session:
        events = session.query(AuditEvent).all()
        actions = {event.action for event in events}
        assert "project.created" in actions
        assert "project.question_added" in actions
        assert "project.task_added" in actions
        assert "project.deleted" in actions


def test_list_projects_excludes_archived_by_default(database: Database) -> None:
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = ProjectService(repositories)
        service.create_project(key="a")
        service.create_project(key="b")
        service.update_project("b", stage=ProjectStage.ARCHIVED)
        visible = service.list_projects()
        assert [p.key for p in visible] == ["a"]
        all_projects = service.list_projects(include_archived=True)
        assert {p.key for p in all_projects} == {"a", "b"}


def test_project_view_counts(database: Database) -> None:
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = ProjectService(repositories)
        service.create_project(key="study-1")
        service.add_question("study-1", text="A")
        service.add_question("study-1", text="B")
        task = service.add_task("study-1", title="T")
        service.update_task("study-1", task.identifier, completed=True)
        view = service.get_project("study-1")
        assert view.question_count == 2
        assert view.total_task_count == 1
        assert view.open_task_count == 0
        assert view.completion_ratio == 1.0