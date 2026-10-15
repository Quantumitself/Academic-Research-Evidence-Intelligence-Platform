"""Tests for the PublicationRepository."""

from __future__ import annotations

import pytest

from academic_platform.infrastructure.database import Database
from academic_platform.infrastructure.database.base import Base
from academic_platform.infrastructure.database.models import Publication
from academic_platform.infrastructure.repositories.publication_repository import (
    PublicationRepository,
)


@pytest.fixture()
def database() -> Database:
    db = Database.in_memory()
    Base.metadata.create_all(db.engine)
    yield db
    db.dispose()


def test_find_by_key_and_doi(database: Database) -> None:
    with database.session() as session:
        repo = PublicationRepository(session)
        repo.add(Publication(key="pub-1", doi="10.1000/xyz"))
    with database.session() as session:
        repo = PublicationRepository(session)
        assert repo.find_by_key("pub-1") is not None
        assert repo.find_by_doi("10.1000/xyz") is not None
        assert repo.find_by_key("missing") is None


def test_add_source_provider_is_idempotent(database: Database) -> None:
    with database.session() as session:
        repo = PublicationRepository(session)
        pub = repo.add(Publication(key="pub-1"))
        repo.add_source_provider(pub, "crossref")
        repo.add_source_provider(pub, "openalex")
        repo.add_source_provider(pub, "crossref")
        assert pub.source_providers_json == '["crossref", "openalex"]'


def test_list_recent(database: Database) -> None:
    with database.session() as session:
        repo = PublicationRepository(session)
        for index in range(5):
            repo.add(Publication(key=f"pub-{index}"))
    with database.session() as session:
        repo = PublicationRepository(session)
        recent = repo.list_recent(limit=2)
        assert len(recent) == 2