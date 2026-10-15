"""Tests for the UserProfile model."""

from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError

from academic_platform.infrastructure.database import Database
from academic_platform.infrastructure.database.base import Base
from academic_platform.infrastructure.database.models import UserProfile


@pytest.fixture()
def database() -> Database:
    db = Database.in_memory()
    Base.metadata.create_all(db.engine)
    yield db
    db.dispose()


def test_create_and_read(database: Database) -> None:
    with database.session() as session:
        profile = UserProfile(
            key="alice",
            display_name="Alice",
            institution="Example University",
        )
        session.add(profile)
        session.flush()
        identifier = profile.id
    with database.session() as session:
        loaded = session.get(UserProfile, identifier)
        assert loaded is not None
        assert loaded.key == "alice"
        assert loaded.display_name == "Alice"
        assert loaded.version == 1


def test_key_unique(database: Database) -> None:
    from academic_platform.infrastructure.database import DatabaseError

    with database.session() as session:
        session.add(UserProfile(key="alice"))
    with pytest.raises(DatabaseError):
        with database.session() as session:
            session.add(UserProfile(key="alice"))


def test_optional_fields_default_none(database: Database) -> None:
    with database.session() as session:
        profile = UserProfile(key="bob")
        session.add(profile)
        session.flush()
        assert profile.preferred_language is None
        assert profile.institution is None
        assert profile.notes is None