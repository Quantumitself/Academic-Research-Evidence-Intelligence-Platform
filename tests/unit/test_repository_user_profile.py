"""Tests for the UserProfileRepository."""

from __future__ import annotations

import pytest

from academic_platform.infrastructure.database import Database
from academic_platform.infrastructure.database.base import Base
from academic_platform.infrastructure.database.models import UserProfile
from academic_platform.infrastructure.repositories.errors import (
    DuplicateEntityError,
)
from academic_platform.infrastructure.repositories.user_profile_repository import (
    UserProfileRepository,
)


@pytest.fixture()
def database() -> Database:
    db = Database.in_memory()
    Base.metadata.create_all(db.engine)
    yield db
    db.dispose()


def test_find_by_key_returns_none_when_missing(database: Database) -> None:
    with database.session() as session:
        repo = UserProfileRepository(session)
        assert repo.find_by_key("missing") is None


def test_find_by_key_returns_existing(database: Database) -> None:
    with database.session() as session:
        repo = UserProfileRepository(session)
        repo.add(UserProfile(key="alice", display_name="Alice"))
    with database.session() as session:
        repo = UserProfileRepository(session)
        found = repo.find_by_key("alice")
        assert found is not None
        assert found.display_name == "Alice"


def test_get_or_create_by_key_creates_once(database: Database) -> None:
    with database.session() as session:
        repo = UserProfileRepository(session)
        profile, created = repo.get_or_create_by_key("alice", display_name="Alice")
        assert created is True
        assert profile.display_name == "Alice"
    with database.session() as session:
        repo = UserProfileRepository(session)
        profile, created = repo.get_or_create_by_key("alice", display_name="Other")
        assert created is False
        assert profile.display_name == "Alice"


def test_get_or_create_ignores_defaults_when_existing(database: Database) -> None:
    with database.session() as session:
        repo = UserProfileRepository(session)
        repo.add(UserProfile(key="alice", display_name="Alice"))
    with database.session() as session:
        repo = UserProfileRepository(session)
        profile, created = repo.get_or_create_by_key("alice", display_name="Other")
        assert created is False
        assert profile.display_name == "Alice"


def test_duplicate_key_rejected(database: Database) -> None:
    with database.session() as session:
        repo = UserProfileRepository(session)
        repo.add(UserProfile(key="alice"))
    with pytest.raises(DuplicateEntityError):
        with database.session() as session:
            repo = UserProfileRepository(session)
            repo.add(UserProfile(key="alice"))


def test_list_keys_sorted(database: Database) -> None:
    with database.session() as session:
        repo = UserProfileRepository(session)
        repo.add_all(
            [
                UserProfile(key="charlie"),
                UserProfile(key="alice"),
                UserProfile(key="bob"),
            ]
        )
    with database.session() as session:
        repo = UserProfileRepository(session)
        assert repo.list_keys() == ["alice", "bob", "charlie"]


def test_list_keys_empty(database: Database) -> None:
    with database.session() as session:
        repo = UserProfileRepository(session)
        assert repo.list_keys() == []