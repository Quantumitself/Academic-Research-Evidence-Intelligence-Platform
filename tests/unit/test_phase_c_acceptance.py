"""Phase C acceptance criteria as automated tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from academic_platform.infrastructure.database import Database
from academic_platform.infrastructure.database.base import Base


@pytest.fixture()
def database() -> Database:
    db = Database.in_memory()
    Base.metadata.create_all(db.engine)
    yield db
    db.dispose()


class _ShimmedManager:
    def __init__(self, database: Database) -> None:
        self._database = database
        self._sessions: list = []

    def get(self, key: str):
        from academic_platform.infrastructure.repositories.factory import (
            _REPOSITORY_REGISTRY,
        )

        session = self._database._session_factory()  # noqa: SLF001
        self._sessions.append(session)
        return _REPOSITORY_REGISTRY[key](session)

    def register_all(self, mapping) -> None:
        return None

    def close_all(self) -> None:
        for session in self._sessions:
            try:
                session.commit()
            except Exception:  # noqa: BLE001
                session.rollback()
            finally:
                session.close()
        self._sessions.clear()


def _stub_adapter(key, hits=(), status="ok", message=""):
    from academic_platform.infrastructure.search_providers.adapter import (
        ProviderCapabilities,
        ProviderDescriptor,
        SearchResponse,
        SourceStatus,
        SourceStatusReport,
    )

    class _Stub:
        @property
        def descriptor(self):
            return ProviderDescriptor(
                key=key,
                display_name=key.title(),
                base_url="https://stub.invalid",
                documentation_url="https://stub.invalid/docs",
                provider_kind=key,
                capabilities=ProviderCapabilities(max_results_per_page=100),
            )

        def search(self, request):
            return SearchResponse(
                provider_key=key,
                hits=hits,
                total=len(hits),
                status=SourceStatusReport(
                    provider_key=key,
                    status=SourceStatus(status),
                    result_count=len(hits),
                    message=message,
                ),
            )

        def test_connection(self):
            return SourceStatusReport(provider_key=key, status=SourceStatus.OK)

    return _Stub()


def test_provider_registry_contains_expected(database: Database) -> None:
    import academic_platform.infrastructure.search_providers  # noqa: F401

    from academic_platform.infrastructure.search_providers.registry import (
        default_registry,
    )

    registry = default_registry()
    for key in (
        "crossref",
        "openalex",
        "semantic_scholar",
        "pubmed",
        "europe_pmc",
        "arxiv",
        "null",
    ):
        assert key in registry


def test_orchestrator_deduplicates(database: Database) -> None:
    from academic_platform.application.search_orchestration.orchestrator import (
        SearchOrchestrator,
    )
    from academic_platform.application.search_orchestration.request import (
        SearchOrchestrationRequest,
        SourceSelection,
    )
    from academic_platform.application.search_sources.service import (
        SearchSourceService,
    )
    from academic_platform.application.search_sources.source_config import (
        SourceConfig,
    )
    from academic_platform.infrastructure.search_providers.adapter import (
        SearchHit,
        SearchRequest,
    )
    from academic_platform.infrastructure.search_providers.registry import (
        ProviderRegistry,
    )

    manager = _ShimmedManager(database)
    registry = ProviderRegistry()
    service = SearchSourceService(manager, registry)  # type: ignore[arg-type]
    for key in ("a", "b"):
        service.create(
            SourceConfig(
                key=key,
                provider_key=key,
                display_name=key.title(),
                source_type="builtin",
                base_url="https://api.crossref.org",
            )
        )
    manager.close_all()
    registry.register_instance(
        "a",
        _stub_adapter(
            "a",
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
        _stub_adapter(
            "b",
            hits=(
                SearchHit(
                    provider_key="b",
                    provider_identifier="2",
                    title="T2",
                    doi="10.1000/x",
                ),
            ),
        ),
    )
    manager = _ShimmedManager(database)
    service = SearchSourceService(manager, registry)  # type: ignore[arg-type]
    orchestrator = SearchOrchestrator(manager, service, registry)  # type: ignore[arg-type]
    response = orchestrator.execute(
        SearchOrchestrationRequest(
            search_request=SearchRequest(query="ml"),
            selection=SourceSelection(all_enabled=True),
        )
    )
    manager.close_all()
    assert len(response.hits) == 2
    assert len(response.publications) == 1


def test_orchestrator_partial_flag(database: Database) -> None:
    from academic_platform.application.search_orchestration.orchestrator import (
        SearchOrchestrator,
    )
    from academic_platform.application.search_orchestration.request import (
        SearchOrchestrationRequest,
        SourceSelection,
    )
    from academic_platform.application.search_sources.service import (
        SearchSourceService,
    )
    from academic_platform.application.search_sources.source_config import (
        SourceConfig,
    )
    from academic_platform.infrastructure.search_providers.adapter import (
        SearchRequest,
    )
    from academic_platform.infrastructure.search_providers.registry import (
        ProviderRegistry,
    )

    manager = _ShimmedManager(database)
    registry = ProviderRegistry()
    service = SearchSourceService(manager, registry)  # type: ignore[arg-type]
    for key in ("ok", "fail"):
        service.create(
            SourceConfig(
                key=key,
                provider_key=key,
                display_name=key.title(),
                source_type="builtin",
                base_url="https://api.crossref.org",
            )
        )
    manager.close_all()
    registry.register_instance("ok", _stub_adapter("ok"))
    registry.register_instance(
        "fail", _stub_adapter("fail", status="failed", message="boom")
    )
    manager = _ShimmedManager(database)
    service = SearchSourceService(manager, registry)  # type: ignore[arg-type]
    orchestrator = SearchOrchestrator(manager, service, registry)  # type: ignore[arg-type]
    response = orchestrator.execute(
        SearchOrchestrationRequest(
            search_request=SearchRequest(query="ml"),
            selection=SourceSelection(all_enabled=True),
        )
    )
    manager.close_all()
    assert response.partial is True


def test_saved_search_round_trip(database: Database) -> None:
    from academic_platform.application.saved_searches.model import SavedSearch
    from academic_platform.application.saved_searches.service import (
        SavedSearchService,
    )

    manager = _ShimmedManager(database)
    service = SavedSearchService(manager)  # type: ignore[arg-type]
    service.create(SavedSearch(key="a", name="A", query_text="ml"))
    loaded = service.get_by_key("a")
    manager.close_all()
    assert loaded.query_text == "ml"