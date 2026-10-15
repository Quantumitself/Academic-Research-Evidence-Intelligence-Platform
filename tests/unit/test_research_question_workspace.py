"""Tests for the research-question workspace service."""

from __future__ import annotations

import json

import pytest

from academic_platform.application.research_questions.errors import (
    ResearchQuestionWorkspaceNotFoundError,
    ResearchQuestionWorkspaceValidationError,
)
from academic_platform.application.research_questions.model import (
    QuestionKind,
)
from academic_platform.application.research_questions.service import (
    ResearchQuestionWorkspaceService,
)
from academic_platform.infrastructure.database import Database
from academic_platform.infrastructure.database.base import Base
from academic_platform.infrastructure.database.models import (
    AuditEvent,
    ResearchProject,
    ResearchQuestion,
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


def _seed_project(database: Database, key: str = "study-1") -> None:
    with database.session() as session:
        session.add(ResearchProject(key=key, title="Study", topic="A topic"))


def _service(database: Database) -> ResearchQuestionWorkspaceService:
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        return ResearchQuestionWorkspaceService(repositories)


def test_attach_project_loads_topic(database: Database) -> None:
    _seed_project(database)
    service = _service(database)
    draft = service.attach_project("study-1")
    assert draft.project_key == "study-1"
    assert draft.topic == "A topic"


def test_attach_missing_project_raises(database: Database) -> None:
    service = _service(database)
    with pytest.raises(ResearchQuestionWorkspaceNotFoundError):
        service.attach_project("missing")


def test_set_primary_question_creates_row(database: Database) -> None:
    _seed_project(database)
    service = _service(database)
    service.attach_project("study-1")
    draft = service.set_primary_question("What is the effect?")
    assert draft.primary_question == "What is the effect?"
    with database.session() as session:
        rows = session.query(ResearchQuestion).all()
        assert len(rows) == 1
        assert rows[0].is_primary == 1


def test_set_primary_question_updates_existing(database: Database) -> None:
    _seed_project(database)
    service = _service(database)
    service.attach_project("study-1")
    service.set_primary_question("First?")
    service.set_primary_question("Second?")
    with database.session() as session:
        rows = session.query(ResearchQuestion).all()
        assert len(rows) == 1
        assert rows[0].text == "Second?"


def test_add_secondary_question(database: Database) -> None:
    _seed_project(database)
    service = _service(database)
    service.attach_project("study-1")
    view = service.add_question("A sub question?", kind=QuestionKind.SUB)
    assert view.kind is QuestionKind.SUB
    assert view.is_primary is False


def test_add_question_rejects_empty(database: Database) -> None:
    _seed_project(database)
    service = _service(database)
    service.attach_project("study-1")
    with pytest.raises(ResearchQuestionWorkspaceValidationError):
        service.add_question("   ")


def test_add_question_rejects_overlong(database: Database) -> None:
    _seed_project(database)
    service = _service(database)
    service.attach_project("study-1")
    with pytest.raises(ResearchQuestionWorkspaceValidationError):
        service.add_question("x" * 5000)


def test_update_question(database: Database) -> None:
    _seed_project(database)
    service = _service(database)
    service.attach_project("study-1")
    view = service.add_question("Old?")
    updated = service.update_question(view.identifier, text="New?")
    assert updated.text == "New?"


def test_remove_question(database: Database) -> None:
    _seed_project(database)
    service = _service(database)
    service.attach_project("study-1")
    view = service.add_question("Q?")
    service.remove_question(view.identifier)
    draft = service.current_draft()
    assert all(q.identifier != view.identifier for q in draft.questions)


def test_promote_to_primary(database: Database) -> None:
    _seed_project(database)
    service = _service(database)
    service.attach_project("study-1")
    service.set_primary_question("Original?")
    view = service.add_question("Candidate?")
    service.promote_to_primary(view.identifier)
    draft = service.current_draft()
    assert draft.primary_question == "Candidate?"
    with database.session() as session:
        rows = session.query(ResearchQuestion).all()
        primaries = [r for r in rows if r.is_primary]
        assert len(primaries) == 1
        assert primaries[0].text == "Candidate?"


def test_workspace_fields_persist(database: Database) -> None:
    _seed_project(database)
    service = _service(database)
    service.attach_project("study-1")
    service.set_problem("A problem")
    service.set_gap("A gap")
    with database.session() as session:
        project = session.query(ResearchProject).one()
        metadata = json.loads(project.project_metadata or "{}")
        workspace = metadata["research_question_workspace"]
        assert workspace["problem"] == "A problem"
        assert workspace["gap"] == "A gap"


def test_validation_reports_missing_primary(database: Database) -> None:
    _seed_project(database)
    service = _service(database)
    service.attach_project("study-1")
    report = service.validation_report()
    assert not report.is_valid
    assert any(issue.field == "primary_question" for issue in report.errors)


def test_validation_warns_on_vague_terms(database: Database) -> None:
    _seed_project(database)
    service = _service(database)
    service.attach_project("study-1")
    service.set_primary_question("How do things affect stuff?")
    report = service.validation_report()
    assert any(
        "vague" in issue.message.lower() for issue in report.warnings
    )


def test_validation_warns_on_non_question(database: Database) -> None:
    _seed_project(database)
    service = _service(database)
    service.attach_project("study-1")
    service.set_primary_question("This is a statement.")
    report = service.validation_report()
    assert any(
        "question mark" in issue.message.lower() for issue in report.warnings
    )


def test_audit_events_recorded(database: Database) -> None:
    _seed_project(database)
    service = _service(database)
    service.attach_project("study-1")
    service.set_primary_question("What?")
    service.add_question("Sub?")
    with database.session() as session:
        actions = {event.action for event in session.query(AuditEvent).all()}
        assert "question.primary_changed" in actions
        assert "question.added" in actions