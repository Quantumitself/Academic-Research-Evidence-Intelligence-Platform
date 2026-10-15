"""Tests for the Publication model."""

from __future__ import annotations

import pytest

from academic_platform.infrastructure.database import DatabaseError

from academic_platform.infrastructure.database import Database
from academic_platform.infrastructure.database.base import Base
from academic_platform.infrastructure.database.models import Publication


@pytest.fixture()
def database() -> Database:
    db = Database.in_memory()
    Base.metadata.create_all(db.engine)
    yield db
    db.dispose()


def test_create_and_read(database: Database) -> None:
    with database.session() as session:
        publication = Publication(
            key="pub-1",
            doi="10.1000/xyz",
            title="A Study",
            year=2023,
        )
        session.add(publication)
        session.flush()
        identifier = publication.id
    with database.session() as session:
        loaded = session.get(Publication, identifier)
        assert loaded is not None
        assert loaded.doi == "10.1000/xyz"
        assert loaded.source_providers_json == "[]"


def test_key_unique(database: Database) -> None:
    with database.session() as session:
        session.add(Publication(key="pub-1", title="A"))
    with pytest.raises(DatabaseError):
        with database.session() as session:
            session.add(Publication(key="pub-1", title="B"))


def test_doi_unique_when_present(database: Database) -> None:
    with database.session() as session:
        session.add(Publication(key="pub-1", doi="10.1000/xyz", title="A"))
    with pytest.raises(DatabaseError):
        with database.session() as session:
            session.add(Publication(key="pub-2", doi="10.1000/xyz", title="B"))


def test_multiple_null_dois_allowed(database: Database) -> None:
    with database.session() as session:
        session.add(Publication(key="pub-1", title="A"))
        session.add(Publication(key="pub-2", title="B"))
    with database.session() as session:
        assert session.query(Publication).count() == 2