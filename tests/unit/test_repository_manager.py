"""Tests for the repository manager."""

from __future__ import annotations

import pytest

from academic_platform.infrastructure.database import Database
from academic_platform.infrastructure.database.base import Base
from academic_platform.infrastructure.repositories.base import Repository
from academic_platform.infrastructure.repositories.errors import RepositoryError
from academic_platform.infrastructure.repositories.manager import RepositoryManager
from tests.unit.test_repository_base import _Item, _ItemRepository


@pytest.fixture()
def database() -> Database:
    db = Database.in_memory()
    Base.metadata.create_all(db.engine)
    yield db
    db.dispose()


def test_get_unregistered_key_raises(database: Database) -> None:
    with database.session() as session:
        manager = RepositoryManager(session)
        with pytest.raises(RepositoryError):
            manager.get("nonexistent")


def test_register_and_get(database: Database) -> None:
    with database.session() as session:
        manager = RepositoryManager(session)
        manager.register("items", _ItemRepository)
        repo = manager.get("items")
        assert isinstance(repo, _ItemRepository)


def test_instances_cached(database: Database) -> None:
    with database.session() as session:
        manager = RepositoryManager(session)
        manager.register("items", _ItemRepository)
        assert manager.get("items") is manager.get("items")


def test_register_replaces_cached_instance(database: Database) -> None:
    class _AltRepository(Repository[_Item]):
        entity = _Item

    with database.session() as session:
        manager = RepositoryManager(session)
        manager.register("items", _ItemRepository)
        first = manager.get("items")
        manager.register("items", _AltRepository)
        second = manager.get("items")
        assert second is not first
        assert isinstance(second, _AltRepository)


def test_registered_keys_sorted(database: Database) -> None:
    with database.session() as session:
        manager = RepositoryManager(session)
        manager.register("zeta", _ItemRepository)
        manager.register("alpha", _ItemRepository)
        assert manager.registered_keys() == ("alpha", "zeta")


def test_clear_cache(database: Database) -> None:
    with database.session() as session:
        manager = RepositoryManager(session)
        manager.register("items", _ItemRepository)
        first = manager.get("items")
        manager.clear_cache()
        second = manager.get("items")
        assert first is not second


def test_session_property(database: Database) -> None:
    with database.session() as session:
        manager = RepositoryManager(session)
        assert manager.session is session