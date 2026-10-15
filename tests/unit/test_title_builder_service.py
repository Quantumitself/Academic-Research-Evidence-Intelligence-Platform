"""Tests for the title builder service."""

from __future__ import annotations

import pytest

from academic_platform.application.title_builder.errors import (
    TitleBuilderNotFoundError,
)
from academic_platform.application.title_builder.model import (
    TitleState,
)
from academic_platform.application.title_builder.service import (
    TitleBuilderService,
)
from academic_platform.application.topic_workspace.model import (
    TopicDraft,
    TopicField,
)
from academic_platform.infrastructure.database import Database
from academic_platform.infrastructure.database.base import Base
from academic_platform.infrastructure.database.models import (
    AuditEvent,
    ResearchProject,
    ResearchTitleCandidate,
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
        session.add(ResearchProject(key=key, title="Study"))


def _service(database: Database) -> TitleBuilderService:
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        return TitleBuilderService(repositories)


def _draft(**overrides) -> TopicDraft:
    values = {field.value: "" for field in TopicField}
    values.update(overrides)
    return TopicDraft(project_key="study-1", values=values)


def test_generate_persists_candidates(database: Database) -> None:
    _seed_project(database)
    service = _service(database)
    candidates = service.generate_for_project(
        "study-1", _draft(broad_subject="remote work")
    )
    assert candidates
    with database.session() as session:
        rows = session.query(ResearchTitleCandidate).all()
        assert len(rows) == len(candidates)


def test_generate_replaces_proposed_only(database: Database) -> None:
    _seed_project(database)
    service = _service(database)
    candidates = service.generate_for_project(
        "study-1", _draft(broad_subject="remote work")
    )
    # Accept the first candidate.
    first = candidates[0]
    service.accept_candidate("study-1", _row_id(first))
    # Regenerate.
    service.generate_for_project(
        "study-1", _draft(broad_subject="remote work and team cohesion")
    )
    # The accepted candidate must still be present.
    rows = service.list_candidates("study-1")
    assert any(c.state is TitleState.ACCEPTED for c in rows)


def test_accept_candidate(database: Database) -> None:
    _seed_project(database)
    service = _service(database)
    candidates = service.generate_for_project(
        "study-1", _draft(broad_subject="remote work")
    )
    first = candidates[0]
    updated = service.accept_candidate("study-1", _row_id(first))
    assert updated.state is TitleState.ACCEPTED


def test_reject_candidate(database: Database) -> None:
    _seed_project(database)
    service = _service(database)
    candidates = service.generate_for_project(
        "study-1", _draft(broad_subject="remote work")
    )
    updated = service.reject_candidate("study-1", _row_id(candidates[0]))
    assert updated.state is TitleState.REJECTED


def test_remove_candidate(database: Database) -> None:
    _seed_project(database)
    service = _service(database)
    candidates = service.generate_for_project(
        "study-1", _draft(broad_subject="remote work")
    )
    target = _row_id(candidates[0])
    service.remove_candidate("study-1", target)
    remaining = service.list_candidates("study-1")
    assert all(_row_id(c) != target for c in remaining)


def test_unknown_project_raises(database: Database) -> None:
    service = _service(database)
    with pytest.raises(TitleBuilderNotFoundError):
        service.generate_for_project(
            "missing", _draft(broad_subject="x")
        )


def test_audit_events_recorded(database: Database) -> None:
    _seed_project(database)
    service = _service(database)
    candidates = service.generate_for_project(
        "study-1", _draft(broad_subject="remote work"), actor="alice"
    )
    service.accept_candidate(
        "study-1", _row_id(candidates[0]), actor="alice"
    )
    service.reject_candidate(
        "study-1", _row_id(candidates[-1]), actor="alice"
    )
    with database.session() as session:
        actions = {event.action for event in session.query(AuditEvent).all()}
        assert "title.generated" in actions
        assert "title.accepted" in actions
        assert "title.rejected" in actions


def test_preview_does_not_persist(database: Database) -> None:
    _seed_project(database)
    service = _service(database)
    report = service.preview(_draft(broad_subject="remote work"))
    assert report.candidate_count > 0
    with database.session() as session:
        assert session.query(ResearchTitleCandidate).count() == 0


def _row_id(candidate) -> int:
    identifier = candidate.identifier
    if identifier.startswith("row."):
        try:
            return int(identifier.split(".", 1)[1])
        except (ValueError, IndexError):
            return 0
    return 0