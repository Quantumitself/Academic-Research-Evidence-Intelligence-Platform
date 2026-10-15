"""Tests for the research-history service."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from academic_platform.application.research_history.errors import (
    ResearchHistoryNotFoundError,
    ResearchHistoryValidationError,
)
from academic_platform.application.research_history.model import (
    HistoryQuery,
    HistorySearchStatus,
)
from academic_platform.application.research_history.service import (
    ResearchHistoryService,
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


class _StubOrchestrator:
    """A deterministic orchestrator that returns fixed publications."""

    def __init__(self, publications_per_query: int = 3) -> None:
        self._per_query = publications_per_query

    def execute(self, request):
        # Produce a synthetic response compatible with the service's
        # expectations. The response is a simple object with the fields
        # the service reads.
        from academic_platform.application.publications.model import (
            CanonicalPublication,
        )
        from academic_platform.application.search_orchestration.response import (
            SearchOrchestrationResponse,
            SourceOutcome,
            SourceOutcomeStatus,
        )

        query = request.search_request.query
        publications = []
        for index in range(self._per_query):
            publications.append(
                CanonicalPublication(
                    key=f"pub.{query}.{index}",
                    title=f"{query.title()} paper {index}",
                    abstract=f"An abstract about {query}.",
                    authors=("A. Author",),
                    year=2010 + index * 5,
                    venue="Journal",
                    source_providers=("stub",),
                )
            )
        outcomes = (
            SourceOutcome(
                source_key="stub",
                provider_key="stub",
                display_name="Stub",
                status=SourceOutcomeStatus.OK,
                result_count=len(publications),
            ),
        )
        return SearchOrchestrationResponse(
            query=query,
            scope="remote",
            outcomes=outcomes,
            publications=tuple(publications),
        )


@pytest.fixture()
def database() -> Database:
    db = Database.in_memory()
    Base.metadata.create_all(db.engine)
    yield db
    db.dispose()


def _seed_project(database: Database, key: str = "study-1") -> None:
    with database.session() as session:
        session.add(ResearchProject(key=key, title="Study", topic="Topic"))


def _service(
    database: Database,
    orchestrator=None,
) -> ResearchHistoryService:
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        return ResearchHistoryService(
            repositories,
            orchestrator_factory=(lambda: orchestrator) if orchestrator else None,
        )


def test_attach_project_mirrors_topic(database: Database) -> None:
    _seed_project(database)
    service = _service(database)
    draft = service.attach_project("study-1")
    assert draft.topic == "Topic"


def test_attach_missing_project_raises(database: Database) -> None:
    service = _service(database)
    with pytest.raises(ResearchHistoryNotFoundError):
        service.attach_project("missing")


def test_set_topic_persists(database: Database) -> None:
    _seed_project(database)
    service = _service(database)
    service.attach_project("study-1")
    service.set_topic("study-1", "New topic")
    draft = service.current_draft("study-1")
    assert draft.topic == "New topic"


def test_set_topic_rejects_overlong(database: Database) -> None:
    _seed_project(database)
    service = _service(database)
    service.attach_project("study-1")
    with pytest.raises(ResearchHistoryValidationError):
        service.set_topic("study-1", "x" * 2000)


def test_add_and_remove_synonyms(database: Database) -> None:
    _seed_project(database)
    service = _service(database)
    service.attach_project("study-1")
    service.add_synonym("study-1", "equivalence")
    service.add_synonym("study-1", "invariance")
    draft = service.current_draft("study-1")
    assert draft.synonyms == ("equivalence", "invariance")
    service.remove_synonym("study-1", "equivalence")
    draft = service.current_draft("study-1")
    assert draft.synonyms == ("invariance",)


def test_add_user_query_persists(database: Database) -> None:
    _seed_project(database)
    service = _service(database)
    service.attach_project("study-1")
    service.set_topic("study-1", "measurement invariance")
    service.add_user_query("study-1", "custom query")
    proposed = service.propose_queries("study-1")
    assert any(q.is_user_defined and q.text == "custom query" for q in proposed)


def test_remove_user_query(database: Database) -> None:
    _seed_project(database)
    service = _service(database)
    service.attach_project("study-1")
    service.set_topic("study-1", "topic")
    service.add_user_query("study-1", "custom query")
    proposed = service.pro