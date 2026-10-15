"""Tests for the SearchSession and SearchResult models."""

from __future__ import annotations

import pytest

from academic_platform.infrastructure.database import DatabaseError

from academic_platform.infrastructure.database import Database
from academic_platform.infrastructure.database.base import Base
from academic_platform.infrastructure.database.models import (
    Publication,
    SearchResult,
    SearchSession,
)


@pytest.fixture()
def database() -> Database:
    db = Database.in_memory()
    Base.metadata.create_all(db.engine)
    yield db
    db.dispose()


def test_create_session(database: Database) -> None:
    with database.session() as session:
        session_row = SearchSession(query_text="ml", scope="remote")
        session.add(session_row)
        session.flush()
        identifier = session_row.id
    with database.session() as session:
        loaded = session.get(SearchSession, identifier)
        assert loaded is not None
        assert loaded.scope == "remote"
        assert loaded.partial == 0


def test_invalid_scope_rejected(database: Database) -> None:
    with pytest.raises(DatabaseError):
        with database.session() as session:
            session.add(SearchSession(scope="bogus"))

def test_search_result_unique_per_session(database: Database) -> None:
    with database.session() as session:
        session_row = SearchSession(query_text="ml")
        session.add(session_row)
        session.flush()
        publication = Publication(key="pub-1")
        session.add(publication)
        session.flush()
        session.add(
            SearchResult(
                session_id=session_row.id,
                publication_id=publication.id,
                provider_key="crossref",
            )
        )
    with pytest.raises(DatabaseError):
        with database.session() as session:
            session.add(
                SearchResult(
                    session_id=1,
                    publication_id=1,
                    provider_key="openalex",
                )
            )

def test_cascade_delete_removes_results(database: Database) -> None:
    with database.session() as session:
        session_row = SearchSession(query_text="ml")
        session.add(session_row)
        session.flush()
        publication = Publication(key="pub-1")
        session.add(publication)
        session.flush()
        session.add(
            SearchResult(
                session_id=session_row.id,
                publication_id=publication.id,
                provider_key="crossref",
            )
        )
    with database.session() as session:
        row = session.get(SearchSession, 1)
        assert row is not None
        session.delete(row)
    with database.session() as session:
        assert session.query(SearchResult).count() == 0