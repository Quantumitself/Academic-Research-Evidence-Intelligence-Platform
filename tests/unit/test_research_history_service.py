"""Tests for the research-history service."""

from __future__ import annotations

import json

import pytest

from academic_platform.application.research_history.errors import (
    ResearchHistoryNotFoundError,
    ResearchHistoryValidationError,
)
from academic_platform.application.research_history.model import (
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
    """Deterministic orchestrator returning fixed publications per query."""

    def __init__(self, publications_per_query: int = 3) -> None:
        self._per_query = publications_per_query

    def execute(self, request):
        from academic_platform.application.publications.model import (
            CanonicalPublication,
        )
        from academic_platform.application.search_orchestration.response import (
            SearchOrchestrationResponse,
            SourceOutcome,
            SourceOutcomeStatus,
        )

        query = request.search_request.query
        publications = tuple(
            CanonicalPublication(
                key=f"pub.{abs(hash(query)) % 100000}.{index}",
                title=f"{query.title()} paper {index}",
                abstract=f"An abstract about {query}.",
                authors=("A. Author",),
                year=2010 + index * 5,
                venue="Journal",
                source_providers=("stub",),
            )
            for index in range(self._per_query)
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
            publications=publications,
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


def _service(database: Database, orchestrator=None) -> ResearchHistoryService:
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


def test_add_synonym_rejects_empty(database: Database) -> None:
    _seed_project(database)
    service = _service(database)
    service.attach_project("study-1")
    with pytest.raises(ResearchHistoryValidationError):
        service.add_synonym("study-1", "   ")


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
    proposed = service.propose_queries("study-1")
    target = next(q for q in proposed if q.text == "custom query")
    service.remove_user_query("study-1", target.identifier)
    proposed = service.propose_queries("study-1")
    assert not any(q.text == "custom query" for q in proposed)


def test_propose_queries_requires_topic(database: Database) -> None:
    _seed_project(database)
    service = _service(database)
    service.attach_project("study-1")
    service.set_topic("study-1", "")
    assert service.propose_queries("study-1") == []


def test_propose_queries_deterministic(database: Database) -> None:
    _seed_project(database)
    service = _service(database)
    service.attach_project("study-1")
    service.set_topic("study-1", "measurement invariance")
    first = [q.identifier for q in service.propose_queries("study-1")]
    second = [q.identifier for q in service.propose_queries("study-1")]
    assert first == second


def test_propose_queries_deduplicates(database: Database) -> None:
    _seed_project(database)
    service = _service(database)
    service.attach_project("study-1")
    service.set_topic("study-1", "measurement invariance")
    service.add_user_query("study-1", "measurement invariance")
    proposed = service.propose_queries("study-1")
    identifiers = [q.identifier for q in proposed]
    assert len(identifiers) == len(set(identifiers))


def test_set_narrative_persists(database: Database) -> None:
    _seed_project(database)
    service = _service(database)
    service.attach_project("study-1")
    service.set_narrative("study-1", "The topic developed over time.")
    draft = service.current_draft("study-1")
    assert draft.narrative == "The topic developed over time."


def test_set_narrative_rejects_overlong(database: Database) -> None:
    _seed_project(database)
    service = _service(database)
    service.attach_project("study-1")
    with pytest.raises(ResearchHistoryValidationError):
        service.set_narrative("study-1", "x" * 20000)


def test_clear_removes_state(database: Database) -> None:
    _seed_project(database)
    service = _service(database)
    service.attach_project("study-1")
    service.set_topic("study-1", "topic")
    service.add_synonym("study-1", "syn")
    service.clear("study-1")
    draft = service.current_draft("study-1")
    assert draft.topic == ""
    assert draft.synonyms == ()


def test_run_query_records_results(database: Database) -> None:
    _seed_project(database)
    orchestrator = _StubOrchestrator(publications_per_query=2)
    service = _service(database, orchestrator=orchestrator)
    service.attach_project("study-1")
    service.set_topic("study-1", "measurement invariance")
    from academic_platform.application.research_history.model import HistoryQuery

    query = HistoryQuery(
        identifier="q.test", text="measurement invariance"
    )
    run = service.run_query("study-1", query)
    assert run.status is HistorySearchStatus.OK
    assert run.result_count == 2
    draft = service.current_draft("study-1")
    assert draft.result_count == 2


def test_run_query_without_orchestrator_raises(database: Database) -> None:
    _seed_project(database)
    service = _service(database)
    service.attach_project("study-1")
    from academic_platform.application.research_history.errors import (
        ResearchHistorySearchError,
    )
    from academic_platform.application.research_history.model import HistoryQuery

    query = HistoryQuery(identifier="q.x", text="anything")
    with pytest.raises(ResearchHistorySearchError):
        service.run_query("study-1", query)


def test_run_all_executes_each_query(database: Database) -> None:
    _seed_project(database)
    orchestrator = _StubOrchestrator(publications_per_query=1)
    service = _service(database, orchestrator=orchestrator)
    service.attach_project("study-1")
    service.set_topic("study-1", "measurement invariance")
    runs = service.run_all("study-1")
    assert runs
    assert all(r.result_count >= 1 for r in runs)


def test_run_all_records_failure_on_error(database: Database) -> None:
    _seed_project(database)

    class _BrokenOrchestrator:
        def execute(self, request):
            raise RuntimeError("boom")

    service = _service(database, orchestrator=_BrokenOrchestrator())
    service.attach_project("study-1")
    service.set_topic("study-1", "topic")
    runs = service.run_all("study-1")
    assert all(r.status is HistorySearchStatus.FAILED for r in runs)
    assert all(r.message for r in runs)


def test_timeline_groups_by_year(database: Database) -> None:
    _seed_project(database)
    orchestrator = _StubOrchestrator(publications_per_query=3)
    service = _service(database, orchestrator=orchestrator)
    service.attach_project("study-1")
    service.set_topic("study-1", "topic")
    from academic_platform.application.research_history.model import HistoryQuery

    service.run_query("study-1", HistoryQuery(identifier="q.a", text="topic"))
    draft = service.current_draft("study-1")
    assert draft.timeline
    assert sum(b.count for b in draft.timeline) == draft.result_count


def test_themes_group_results(database: Database) -> None:
    _seed_project(database)
    orchestrator = _StubOrchestrator(publications_per_query=2)
    service = _service(database, orchestrator=orchestrator)
    service.attach_project("study-1")
    service.set_topic("study-1", "measurement invariance")
    from academic_platform.application.research_history.model import HistoryQuery

    service.run_query(
        "study-1", HistoryQuery(identifier="q.m", text="measurement invariance")
    )
    draft = service.current_draft("study-1")
    assert draft.themes
    assert any(theme.name == "Measurement" for theme in draft.themes)


def test_audit_events_recorded(database: Database) -> None:
    _seed_project(database)
    service = _service(database)
    service.attach_project("study-1")
    service.set_topic("study-1", "topic")
    service.add_synonym("study-1", "syn")
    service.add_user_query("study-1", "custom")
    service.set_narrative("study-1", "narrative")
    with database.session() as session:
        actions = {event.action for event in session.query(AuditEvent).all()}
    assert "history.topic_set" in actions
    assert "history.synonym_added" in actions
    assert "history.query_added" in actions
    assert "history.narrative_updated" in actions


def test_draft_empty_when_untouched(database: Database) -> None:
    _seed_project(database, "untouched")
    service = _service(database)
    draft = service.current_draft("untouched")
    assert draft.topic == ""
    assert draft.synonyms == ()
    assert draft.results == ()


def test_workspace_stored_in_project_metadata(database: Database) -> None:
    _seed_project(database)
    service = _service(database)
    service.attach_project("study-1")
    service.set_topic("study-1", "stored topic")
    with database.session() as session:
        project = session.query(ResearchProject).one()
        metadata = json.loads(project.project_metadata or "{}")
        workspace = metadata["research_history_workspace"]
        assert workspace["topic"] == "stored topic"