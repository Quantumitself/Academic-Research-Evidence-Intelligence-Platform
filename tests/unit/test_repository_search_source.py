"""Tests for the SearchSourceRepository."""

from __future__ import annotations

import pytest

from academic_platform.infrastructure.database import Database
from academic_platform.infrastructure.database.base import Base
from academic_platform.infrastructure.database.models import SearchSource
from academic_platform.infrastructure.database.schemas import SearchSourceCreate
from academic_platform.infrastructure.repositories.search_source_repository import (
    SearchSourceRepository,
)


@pytest.fixture()
def database() -> Database:
    db = Database.in_memory()
    Base.metadata.create_all(db.engine)
    yield db
    db.dispose()


def _create(repo: SearchSourceRepository, **overrides) -> SearchSource:
    payload = {
        "key": overrides.pop("key", "crossref"),
        "provider_key": overrides.pop("provider_key", "crossref"),
        "display_name": overrides.pop("display_name", "Crossref"),
        "source_type": overrides.pop("source_type", "builtin"),
        "base_url": overrides.pop("base_url", "https://api.crossref.org"),
    }
    payload.update(overrides)
    return repo.create(SearchSourceCreate(**payload))


def test_create_and_find(database: Database) -> None:
    with database.session() as session:
        repo = SearchSourceRepository(session)
        _create(repo)
    with database.session() as session:
        repo = SearchSourceRepository(session)
        assert repo.find_by_key("crossref") is not None
        assert repo.find_by_provider_key("crossref") is not None


def test_list_enabled(database: Database) -> None:
    with database.session() as session:
        repo = SearchSourceRepository(session)
        _create(repo, key="a", provider_key="a", display_name="A")
        _create(repo, key="b", provider_key="b", display_name="B")
        disabled = _create(repo, key="c", provider_key="c", display_name="C")
        repo.set_enabled(disabled.id, False)
    with database.session() as session:
        repo = SearchSourceRepository(session)
        enabled = repo.list_enabled()
        assert [s.key for s in enabled] == ["a", "b"]


def test_set_enabled(database: Database) -> None:
    with database.session() as session:
        repo = SearchSourceRepository(session)
        source = _create(repo)
        repo.set_enabled(source.id, False)
        assert source.enabled == 0
        repo.set_enabled(source.id, True)
        assert source.enabled == 1


def test_record_test_result(database: Database) -> None:
    with database.session() as session:
        repo = SearchSourceRepository(session)
        source = _create(repo)
        repo.record_test_result(
            source.id, tested_at="2024-01-01T00:00:00", error=None
        )
        assert source.last_tested_at == "2024-01-01T00:00:00"
        assert source.last_error is None


def test_list_all_ordered(database: Database) -> None:
    with database.session() as session:
        repo = SearchSourceRepository(session)
        _create(repo, key="b", provider_key="b", display_name="Beta")
        _create(repo, key="a", provider_key="a", display_name="Alpha")
    with database.session() as session:
        repo = SearchSourceRepository(session)
        ordered = repo.list_all_ordered()
        assert [s.display_name for s in ordered] == ["Alpha", "Beta"]