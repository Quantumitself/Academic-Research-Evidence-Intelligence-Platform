"""Tests for the search session and result repositories."""

from __future__ import annotations

import pytest

from academic_platform.infrastructure.database import Database
from academic_platform.infrastructure.database.base import Base
from academic_platform.infrastructure.database.models import (
    Publication,
    SearchSession,
)
from academic_platform.infrastructure.database.schemas import (
    SavedSearchQueryCreate,
    SearchSessionCreate,
)
from academic_platform.infrastructure.repositories.publication_repository import (
    PublicationRepository,
)
from academic_platform.infrastructure.repositories.search_session_repository import (
    SavedSearchQueryRepository,
    SearchResultRepository,
    SearchSessionRepository,
)


@pytest.fixture()
def database() -> Database:
    db = Database.in_memory()
    Base.metadata.create_all(db.engine)
    yield db
    db.dispose()


def test_saved_query_create_and_mark(database: Database) -> None:
    with database.session() as session:
        repo = SavedSearchQueryRepository(session)
        query = repo.create(SavedSearchQueryCreate(key="q1", name="A"))
        assert query.last_executed_at is None
        repo.mark_executed(query.id)
        assert query.last_executed_at is not None


def test_saved_query_list_ordered(database: Database) -> None:
    with database.session() as session:
        repo = SavedSearchQueryRepository(session)
        repo.create(SavedSearchQueryCreate(key="b", name="Beta"))
        repo.create(SavedSearchQueryCreate(key="a", name="Alpha"))
    with database.session() as session:
        repo = SavedSearchQueryRepository(session)
        names = [q.name for q in repo.list_all_ordered()]
        assert names == ["Alpha", "Beta"]


def test_session_create_and_record_outcome(database: Database) -> None:
    with database.session() as session:
        repo = SearchSessionRepository(session)
        row = repo.create(SearchSessionCreate(query_text="ml"))
        assert row.result_count == 0
        repo.record_outcome(row.id, result_count=5, partial=True)
        assert row.result_count == 5
        assert row.partial == 1


def test_session_list_recent(database: Database) -> None:
    with database.session() as session:
        repo = SearchSessionRepository(session)
        for index in range(3):
            repo.create(SearchSessionCreate(query_text=f"q{index}"))
    with database.session() as session:
        repo = SearchSessionRepository(session)
        recent = repo.list_recent(limit=2)
        assert len(recent) == 2


def test_result_add_and_list(database: Database) -> None:
    with database.session() as session:
        pub_repo = PublicationRepository(session)
        session_repo = SearchSessionRepository(session)
        result_repo = SearchResultRepository(session)
        pub = pub_repo.add(Publication(key="pub-1"))
        pub2 = pub_repo.add(Publication(key="pub-2"))
        session_row = session_repo.create(SearchSessionCreate(query_text="ml"))
        result_repo.add_result(
            session_row.id, pub.id, "crossref", rank=1, score=0.9
        )
        result_repo.add_result(
            session_row.id, pub2.id, "openalex", rank=2, score=0.7
        )
    with database.session() as session:
        result_repo = SearchResultRepository(session)
        results = result_repo.list_for_session(1)
        assert [r.rank for r in results] == [1, 2]
        assert [r.provider_key for r in results] == ["crossref", "openalex"]


def test_result_duplicate_target_rejected(database: Database) -> None:
    from academic_platform.infrastructure.repositories.errors import (
        DuplicateEntityError,
    )

    with database.session() as session:
        pub_repo = PublicationRepository(session)
        session_repo = SearchSessionRepository(session)
        pub = pub_repo.add(Publication(key="pub-1"))
        session_row = session_repo.create(SearchSessionCreate(query_text="ml"))
    with database.session() as session:
        result_repo = SearchResultRepository(session)
        result_repo.add_result(session_row.id, pub.id, "crossref")
    with pytest.raises(DuplicateEntityError):
        with database.session() as session:
            result_repo = SearchResultRepository(session)
            result_repo.add_result(session_row.id, pub.id, "openalex")


def test_result_publication_ids_for_session(database: Database) -> None:
    with database.session() as session:
        pub_repo = PublicationRepository(session)
        session_repo = SearchSessionRepository(session)
        result_repo = SearchResultRepository(session)
        pub = pub_repo.add(Publication(key="pub-1"))
        session_row = session_repo.create(SearchSessionCreate(query_text="ml"))
        result_repo.add_result(session_row.id, pub.id, "crossref")
    with database.session() as session:
        result_repo = SearchResultRepository(session)
        ids = result_repo.list_publication_ids_for_session(session_row.id)
        assert ids == [pub.id]