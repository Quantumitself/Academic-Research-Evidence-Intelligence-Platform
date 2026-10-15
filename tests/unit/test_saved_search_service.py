"""Tests for the saved-search service."""

from __future__ import annotations

import pytest

from academic_platform.application.saved_searches.errors import (
    SavedSearchError,
    SavedSearchNotFoundError,
)
from academic_platform.application.saved_searches.model import SavedSearch
from academic_platform.application.saved_searches.service import (
    SavedSearchService,
)
from academic_platform.infrastructure.database import Database
from academic_platform.infrastructure.database.base import Base
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


@pytest.fixture()
def service(database: Database) -> SavedSearchService:
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        yield SavedSearchService(repositories)


def test_create_and_list(database: Database) -> None:
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = SavedSearchService(repositories)
        service.create(SavedSearch(key="a", name="Alpha"))
        service.create(SavedSearch(key="b", name="Beta"))
        listed = service.list_all()
        assert [s.key for s in listed] == ["a", "b"]


def test_get_by_key_raises_when_missing(database: Database) -> None:
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = SavedSearchService(repositories)
        with pytest.raises(SavedSearchNotFoundError):
            service.get_by_key("missing")


def test_duplicate_key_raises(database: Database) -> None:
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = SavedSearchService(repositories)
        service.create(SavedSearch(key="a"))

    session = database._session_factory()  # noqa: SLF001
    try:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = SavedSearchService(repositories)
        with pytest.raises(SavedSearchError):
            service.create(SavedSearch(key="a"))
    finally:
        session.rollback()
        session.close()


def test_update_name(database: Database) -> None:
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = SavedSearchService(repositories)
        service.create(SavedSearch(key="a", name="Alpha"))
        updated = service.update("a", name="Alpha v2")
        assert updated.name == "Alpha v2"


def test_update_unknown_key_raises(database: Database) -> None:
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = SavedSearchService(repositories)
        with pytest.raises(SavedSearchNotFoundError):
            service.update("missing", name="x")


def test_delete(database: Database) -> None:
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = SavedSearchService(repositories)
        service.create(SavedSearch(key="a"))
        service.delete("a")
        with pytest.raises(SavedSearchNotFoundError):
            service.get_by_key("a")


def test_mark_executed(database: Database) -> None:
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = SavedSearchService(repositories)
        service.create(SavedSearch(key="a"))
        marked = service.mark_executed("a")
        assert marked.last_executed_at is not None


def test_filters_round_trip(database: Database) -> None:
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = SavedSearchService(repositories)
        service.create(
            SavedSearch(
                key="a",
                filters={"year_from": 2010, "open_access_only": True},
                source_keys=("crossref", "openalex"),
            )
        )
        loaded = service.get_by_key("a")
        assert loaded.filters.get("year_from") == 2010
        assert loaded.source_keys == ("crossref", "openalex")