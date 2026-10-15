"""Tests for the search orchestrator.

The tests use stub adapters registered with a private registry. They do
not exercise the network. The orchestrator's persistence path is
exercised against an in-memory database.
"""

from __future__ import annotations
from collections.abc import Iterator

import pytest

from academic_platform.application.search_orchestration.orchestrator import (
    SearchOrchestrator,
)
from academic_platform.application.search_orchestration.request import (
    SearchOrchestrationRequest,
    SourceSelection,
)
from academic_platform.application.search_orchestration.response import (
    SourceOutcomeStatus,
)
from academic_platform.application.search_sources.service import (
    SearchSourceService,
)
from academic_platform.application.search_sources.source_config import (
    SourceConfig,
)
from academic_platform.infrastructure.database import Database
from academic_platform.infrastructure.database.base import Base
from academic_platform.infrastructure.repositories.factory import (
    _REPOSITORY_REGISTRY,
)
from academic_platform.infrastructure.repositories.manager import (
    RepositoryManager,
)
from academic_platform.infrastructure.search_providers.adapter import (
    ProviderCapabilities,
    ProviderDescriptor,
    SearchProviderAdapter,
    SearchRequest,
    SearchHit,
    SearchResponse,
    SourceStatus,
    SourceStatusReport,
)
from academic_platform.infrastructure.search_providers.registry import (
    ProviderRegistry,
)


class _StubAdapter(SearchProviderAdapter):
    def __init__(
        self,
        *,
        key: str,
        hits: tuple[SearchHit, ...] = (),
        status: SourceStatus = SourceStatus.OK,
        message: str = "",
    ) -> None:
        self._key = key
        self._hits = hits
        self._status = status
        self._message = message

    @property
    def descriptor(self) -> ProviderDescriptor:
        return ProviderDescriptor(
            key=self._key,
            display_name=self._key.title(),
            base_url="https://stub.invalid",
            documentation_url="https://stub.invalid/docs",
            provider_kind=self._key,
            capabilities=ProviderCapabilities(max_results_per_page=100),
        )

    def search(self, request: SearchRequest) -> SearchResponse:
        return SearchResponse(
            provider_key=self._key,
            hits=self._hits,
            total=len(self._hits),
            next_cursor=None,
            status=SourceStatusReport(
                provider_key=self._key,
                status=self._status,
                result_count=len(self._hits),
                message=self._message,
            ),
        )

    def test_connection(self) -> SourceStatusReport:
        return SourceStatusReport(provider_key=self._key, status=SourceStatus.OK)


@pytest.fixture()
def env() -> Iterator[Database]:
    database = Database.in_memory()
    Base.metadata.create_all(database.engine)
    yield database
    database.dispose()


def _build_orchestrator(database: Database):
    """Construct an orchestrator with a private provider registry."""
    from academic_platform.application.search_sources.service import (
        SearchSourceService,
    )
    from academic_platform.infrastructure.repositories.factory import (
        _REPOSITORY_REGISTRY,
    )

    class _Manager:
        def __init__(self, database: Database) -> None:
            self._database = database
            self._sessions: list = []

        def get(self, key: str):
            session = self._database._session_factory()  # noqa: SLF001
            self._sessions.append(session)
            repository_class = _REPOSITORY_REGISTRY[key]
            return repository_class(session)

        def close_all(self) -> None:
            for session in self._sessions:
                try:
                    session.commit()
                except Exception:  # noqa: BLE001
                    session.rollback()
                finally:
                    session.close()
            self._sessions.clear()

    registry = ProviderRegistry()
    manager = _Manager(database)
    service = SearchSourceService(manager, registry)  # type: ignore[arg-type]
    orchestrator = SearchOrchestrator(manager, service, registry)  # type: ignore[arg-type]
    return manager, service, registry, orchestrator


def test_orchestrator_rejects_empty_selection(env) -> None:
    manager, service, registry, orchestrator = _build_orchestrator(env)
    request = SearchOrchestrationRequest(
        search_request=SearchRequest(query="ml"),
        selection=SourceSelection(all_enabled=False, source_keys=("missing",)),
    )
    with pytest.raises(Exception):
        orchestrator.execute(request, saved_query_id=None)
    manager.close_all()


def test_orchestrator_no_session_recording(env) -> None:
    manager, service, registry, orchestrator = _build_orchestrator(env)
    config = SourceConfig(
        key="crossref",
        provider_key="crossref",
        display_name="Crossref",
        source_type="builtin",
        base_url="https://api.crossref.org",
        endpoint="works",
    )
    service.create(config)

    hits = (
        SearchHit(
            provider_key="crossref",
            provider_identifier="10.1000/x",
            title="T",
            doi="10.1000/x",
        ),
    )
    registry.register_instance("crossref", _StubAdapter(key="crossref", hits=hits))

    request = SearchOrchestrationRequest(
        search_request=SearchRequest(query="ml"),
        record_session=False,
    )
    response = orchestrator.execute(request)
    manager.close_all()
    assert len(response.hits) == 1
    assert response.session_id is None


def test_orchestrator_records_session(env) -> None:
    manager, service, registry, orchestrator = _build_orchestrator(env)
    config = SourceConfig(
        key="crossref",
        provider_key="crossref",
        display_name="Crossref",
        source_type="builtin",
        base_url="https://api.crossref.org",
        endpoint="works",
    )
    service.create(config)

    hits = (
        SearchHit(
            provider_key="crossref",
            provider_identifier="10.1000/x",
            title="T",
            doi="10.1000/x",
        ),
    )
    registry.register_instance("crossref", _StubAdapter(key="crossref", hits=hits))

    request = SearchOrchestrationRequest(
        search_request=SearchRequest(query="ml"),
    )
    response = orchestrator.execute(request)
    manager.close_all()
    assert response.session_id is not None
    assert response.publications
    assert response.outcomes[0].status is SourceOutcomeStatus.OK


def test_orchestrator_partial_failure_marks_partial(env) -> None:
    manager, service, registry, orchestrator = _build_orchestrator(env)
    for key in ("a", "b"):
        config = SourceConfig(
            key=key,
            provider_key=key,
            display_name=key.title(),
            source_type="builtin",
            base_url="https://api.crossref.org",
        )
        service.create(config)
    registry.register_instance("a", _StubAdapter(key="a"))
    registry.register_instance(
        "b",
        _StubAdapter(key="b", status=SourceStatus.FAILED, message="boom"),
    )
    request = SearchOrchestrationRequest(
        search_request=SearchRequest(query="ml"),
    )
    response = orchestrator.execute(request)
    manager.close_all()
    assert response.partial is True
    statuses = {o.source_key: o.status for o in response.outcomes}
    assert statuses["a"] is SourceOutcomeStatus.OK
    assert statuses["b"] is SourceOutcomeStatus.FAILED


def test_orchestrator_deduplicates_across_sources(env) -> None:
    manager, service, registry, orchestrator = _build_orchestrator(env)
    for key in ("a", "b"):
        config = SourceConfig(
            key=key,
            provider_key=key,
            display_name=key.title(),
            source_type="builtin",
            base_url="https://api.crossref.org",
        )
        service.create(config)
    registry.register_instance(
        "a",
        _StubAdapter(
            key="a",
            hits=(
                SearchHit(
                    provider_key="a",
                    provider_identifier="1",
                    title="T",
                    doi="10.1000/x",
                ),
            ),
        ),
    )
    registry.register_instance(
        "b",
        _StubAdapter(
            key="b",
            hits=(
                SearchHit(
                    provider_key="b",
                    provider_identifier="2",
                    title="T (duplicate)",
                    doi="10.1000/x",
                ),
            ),
        ),
    )
    request = SearchOrchestrationRequest(
        search_request=SearchRequest(query="ml"),
    )
    response = orchestrator.execute(request)
    manager.close_all()
    assert len(response.hits) == 2
    assert len(response.publications) == 1