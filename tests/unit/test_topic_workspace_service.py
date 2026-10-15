"""Tests for the topic workspace service."""

from __future__ import annotations

import json

import pytest

from academic_platform.application.topic_workspace.errors import (
    TopicWorkspaceNotFoundError,
    TopicWorkspaceValidationError,
)
from academic_platform.application.topic_workspace.model import (
    TopicField,
)
from academic_platform.application.topic_workspace.service import (
    TopicWorkspaceService,
)
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


def _seed_project(database: Database, key: str = "study-1") -> None:
    with database.session() as session:
        session.add(
            ResearchProject(
                key=key,
                title="Study",
                topic="Initial topic",
            )
        )


def _service(database: Database) -> TopicWorkspaceService:
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        return TopicWorkspaceService(repositories)


def test_attach_project_reads_existing_topic(database: Database) -> None:
    _seed_project(database)
    service = _service(database)
    draft = service.attach_project("study-1")
    assert draft.project_key == "study-1"
    assert draft.broad_subject == "Initial topic"


def test_attach_missing_project_raises(database: Database) -> None:
    service = _service(database)
    with pytest.raises(TopicWorkspaceNotFoundError):
        service.attach_project("missing")


def test_set_field_without_attachment(database: Database) -> None:
    service = _service(database)
    draft = service.set_field(
        TopicField.BROAD_SUBJECT, "New subject"
    )
    assert draft.broad_subject == "New subject"
    assert service.attached_project_key is None


def test_set_field_persists_when_attached(database: Database) -> None:
    _seed_project(database)
    service = _service(database)
    service.attach_project("study-1")
    service.set_field(TopicField.BROAD_SUBJECT, "Updated subject")
    # Reopen the project through a new service and confirm the change
    # is visible.
    with database.session() as session:
        project = session.query(ResearchProject).one()
        assert project.topic == "Updated subject"


def test_metadata_round_trip(database: Database) -> None:
    _seed_project(database)
    service = _service(database)
    service.attach_project("study-1")
    service.set_fields(
        {
            TopicField.RESEARCH_PROBLEM: "The problem",
            TopicField.CONTEXT: "The context",
            TopicField.POPULATION: "Adults",
        }
    )
    with database.session() as session:
        project = session.query(ResearchProject).one()
        metadata = json.loads(project.project_metadata)
        workspace = metadata["topic_workspace"]
        assert workspace["research_problem"] == "The problem"
        assert workspace["context"] == "The context"
        assert workspace["population"] == "Adults"


def test_reload_preserves_extended_fields(database: Database) -> None:
    _seed_project(database)
    service = _service(database)
    service.attach_project("study-1")
    service.set_fields(
        {
            TopicField.BROAD_SUBJECT: "Subject",
            TopicField.KEY_CONCEPTS: "Concept A, Concept B",
        }
    )
    # Reopen through a new service instance.
    second = _service(database)
    draft = second.attach_project("study-1")
    assert draft.broad_subject == "Subject"
    assert draft.key_concepts == "Concept A, Concept B"


def test_completeness_reports_missing_essential(database: Database) -> None:
    _seed_project(database)
    service = _service(database)
    service.attach_project("study-1")
    service.clear()
    report = service.completeness()
    assert report.is_ready is False
    assert TopicField.BROAD_SUBJECT in report.missing_essential
    assert TopicField.RESEARCH_PROBLEM in report.missing_essential


def test_completeness_ready_when_essentials_present(database: Database) -> None:
    _seed_project(database)
    service = _service(database)
    service.attach_project("study-1")
    service.set_fields(
        {
            TopicField.BROAD_SUBJECT: "Subject",
            TopicField.RESEARCH_PROBLEM: "Problem",
        }
    )
    report = service.completeness()
    assert report.is_ready is True
    assert report.populated_count == 2


def test_clear_removes_fields(database: Database) -> None:
    _seed_project(database)
    service = _service(database)
    service.attach_project("study-1")
    service.set_fields({TopicField.BROAD_SUBJECT: "Subject"})
    draft = service.clear()
    assert draft.is_empty
    with database.session() as session:
        project = session.query(ResearchProject).one()
        assert project.topic == ""


def test_validation_rejects_overlong_value(database: Database) -> None:
    service = _service(database)
    with pytest.raises(TopicWorkspaceValidationError):
        service.set_field(TopicField.TIME_PERIOD, "x" * 1000)


def test_merge_into_project_merges_values(database: Database) -> None:
    _seed_project(database)
    with database.session() as session:
        project = session.query(ResearchProject).one()
        project.topic = "Existing subject"
    service = _service(database)
    service.set_field(TopicField.RESEARCH_PROBLEM, "New problem")
    draft = service.merge_into_project("study-1")
    assert draft.project_key == "study-1"
    assert draft.broad_subject == "Existing subject"
    assert draft.research_problem == "New problem"


def test_audit_events_recorded(database: Database) -> None:
    _seed_project(database)
    service = _service(database)
    service.attach_project("study-1", actor="alice")
    service.set_field(TopicField.BROAD_SUBJECT, "Subject", actor="alice")
    service.detach_project(actor="alice")
    with database.session() as session:
        actions = {event.action for event in session.query(AuditEvent).all()}
        assert "topic.attached" in actions
        assert "topic.updated" in actions
        assert "topic.detached" in actions


def test_detach_preserves_values(database: Database) -> None:
    _seed_project(database)
    service = _service(database)
    service.attach_project("study-1")
    service.set_field(TopicField.BROAD_SUBJECT, "Subject")
    draft = service.detach_project()
    assert draft.project_key is None
    assert draft.broad_subject == "Subject"