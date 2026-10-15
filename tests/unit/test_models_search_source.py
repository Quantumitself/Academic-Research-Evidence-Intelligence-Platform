"""Tests for the SearchSource model."""

from __future__ import annotations

import pytest

from academic_platform.infrastructure.database import DatabaseError

from academic_platform.infrastructure.database import Database
from academic_platform.infrastructure.database.base import Base
from academic_platform.infrastructure.database.models import SearchSource


@pytest.fixture()
def database() -> Database:
    db = Database.in_memory()
    Base.metadata.create_all(db.engine)
    yield db
    db.dispose()


def _valid_source(**overrides) -> SearchSource:
    defaults = {
        "key": "crossref",
        "provider_key": "crossref",
        "display_name": "Crossref",
        "source_type": "builtin",
        "base_url": "https://api.crossref.org",
    }
    defaults.update(overrides)
    return SearchSource(**defaults)


def test_create_and_read(database: Database) -> None:
    with database.session() as session:
        source = _valid_source()
        session.add(source)
        session.flush()
        identifier = source.id
    with database.session() as session:
        loaded = session.get(SearchSource, identifier)
        assert loaded is not None
        assert loaded.enabled == 1
        assert loaded.auth_type == "none"


def test_key_unique(database: Database) -> None:
    with database.session() as session:
        session.add(_valid_source())
    with pytest.raises(DatabaseError):
        with database.session() as session:
            session.add(_valid_source(provider_key="other"))


def test_provider_key_unique(database: Database) -> None:
    with database.session() as session:
        session.add(_valid_source())
    with pytest.raises(DatabaseError):
        with database.session() as session:
            session.add(_valid_source(key="other", provider_key="crossref"))


def test_invalid_source_type_rejected(database: Database) -> None:
    with pytest.raises(DatabaseError):
        with database.session() as session:
            session.add(_valid_source(source_type="bogus"))


def test_invalid_auth_type_rejected(database: Database) -> None:
    with pytest.raises(DatabaseError):
        with database.session() as session:
            session.add(_valid_source(auth_type="bogus"))