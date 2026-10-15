"""Tests that the search source service exposes the publication service."""

from __future__ import annotations

from academic_platform.application.publications.service import (
    PublicationService,
)
from academic_platform.application.search_sources.service import (
    SearchSourceService,
)
from academic_platform.infrastructure.database import Database
from academic_platform.infrastructure.database.base import Base
from academic_platform.infrastructure.repositories.factory import (
    _REPOSITORY_REGISTRY,
)
from academic_platform.infrastructure.repositories.manager import (
    RepositoryManager,
)
from academic_platform.infrastructure.search_providers.registry import (
    ProviderRegistry,
)


def test_publication_service_exposed() -> None:
    database = Database.in_memory()
    try:
        Base.metadata.create_all(database.engine)
        with database.session() as session:
            repositories = RepositoryManager(session)
            repositories.register_all(dict(_REPOSITORY_REGISTRY))
            registry = ProviderRegistry()
            service = SearchSourceService(repositories, registry)
            assert isinstance(service.publications, PublicationService)
    finally:
        database.dispose()