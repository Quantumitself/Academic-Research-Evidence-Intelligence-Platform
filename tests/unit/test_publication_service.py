"""Tests for the publication service."""

from __future__ import annotations
from collections.abc import Iterator

import json

import pytest

from academic_platform.application.publications.model import (
    CanonicalPublication,
)
from academic_platform.application.publications.service import (
    PublicationService,
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
    SearchHit,
)


@pytest.fixture()
def database() -> Iterator[Database]:
    db = Database.in_memory()
    Base.metadata.create_all(db.engine)
    yield db
    db.dispose()


@pytest.fixture()
def service(database: Database) -> Iterator[PublicationService]:
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        yield PublicationService(repositories)


def _hit(**overrides) -> SearchHit:
    defaults = {
        "provider_key": "crossref",
        "provider_identifier": "10.1000/xyz",
        "title": "A Title",
        "doi": "10.1000/XYZ",
        "authors": ("A. Author",),
        "year": 2020,
    }
    defaults.update(overrides)
    return SearchHit(**defaults)


def test_persist_new_publication(database: Database) -> None:
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = PublicationService(repositories)
        publication = CanonicalPublication(
            key="doi:x",
            doi="x",
            title="T",
            authors=("A",),
            source_providers=("crossref",),
        )
        stored = service.persist((publication,))
        assert len(stored) == 1
        assert stored[0].key == "doi:x"


def test_persist_is_idempotent_for_same_doi(database: Database) -> None:
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = PublicationService(repositories)
        publication = CanonicalPublication(
            key="doi:x",
            doi="x",
            title="T",
            source_providers=("crossref",),
        )
        first = service.persist((publication,))[0]
        second = service.persist((publication,))[0]
        assert first.id == second.id


def test_persist_merges_providers(database: Database) -> None:
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = PublicationService(repositories)
        first = CanonicalPublication(
            key="doi:x",
            doi="x",
            source_providers=("crossref",),
        )
        second = CanonicalPublication(
            key="doi:x",
            doi="x",
            source_providers=("openalex",),
        )
        service.persist((first,))
        stored = service.persist((second,))[0]
        providers = json.loads(stored.source_providers_json)
        assert sorted(providers) == ["crossref", "openalex"]


def test_normalize_and_store(database: Database) -> None:
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = PublicationService(repositories)
        hits = [
            _hit(doi="10.1000/one", title="First"),
            _hit(
                provider_key="openalex",
                provider_identifier="W1",
                doi="10.1000/one",
                title="",  # duplicate, no title
            ),
        ]
        normalization, deduplication, stored = service.normalize_and_store(hits)
        assert normalization.publication_count == 2
        assert deduplication.publication_count == 1
        assert deduplication.merged_count == 1
        assert len(stored) == 1
        assert stored[0].title == "First"


def test_persist_preserves_user_edits(database: Database) -> None:
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = PublicationService(repositories)
        publication = CanonicalPublication(
            key="doi:x",
            doi="x",
            title="Original",
        )
        stored = service.persist((publication,))[0]
        stored.title = "User Edited"
        service.persist(
            (
                CanonicalPublication(
                    key="doi:x",
                    doi="x",
                    title="From Provider",
                ),
            )
        )
        assert stored.title == "User Edited"


def test_find_existing_key_by_doi(database: Database) -> None:
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = PublicationService(repositories)
        service.persist(
            (
                CanonicalPublication(
                    key="doi:x",
                    doi="x",
                    title="T",
                ),
            )
        )
        found = service.find_existing_key(
            CanonicalPublication(key="other", doi="x")
        )
        assert found == "doi:x"


def test_find_existing_key_absent(database: Database) -> None:
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = PublicationService(repositories)
        assert (
            service.find_existing_key(
                CanonicalPublication(key="doi:missing", doi="missing")
            )
            is None
        )