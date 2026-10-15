"""Tests for the SavedSearchQuery model."""

from __future__ import annotations

import pytest

from academic_platform.infrastructure.database import DatabaseError

from academic_platform.infrastructure.database import Database
from academic_platform.infrastructure.database.base import Base
from academic_platform.infrastructure.database.models import SavedSearchQuery


@pytest.fixture()
def database() -> Database:
    db = Database.in_memory()
    Base.metadata.create_all(db.engine)
    yield db
    db.dispose()


def test_create_and_read(database: Database) -> None:
    with database.session() as session:
        query = SavedSearchQuery(
            key="q1",
            name="My search",
            query_text="machine learning",
        )
        session.add(query)
        session.flush()
        identifier = query.id
    with database.session() as session:
        loaded = session.get(SavedSearchQuery, identifier)
        assert loaded is not None
        assert loaded.scope == "all"
        assert loaded.source_ids_json == "[]"


def test_key_unique(database: Database) -> None:
    with database.session() as session:
        session.add(SavedSearchQuery(key="q1"))
    with pytest.raises(DatabaseError):
        with database.session() as session:
            session.add(SavedSearchQuery(key="q1"))


def test_invalid_scope_rejected(database: Database) -> None:
    with pytest.raises(DatabaseError):
        with database.session() as session:
            session.add(SavedSearchQuery(key="q1", scope="bogus"))