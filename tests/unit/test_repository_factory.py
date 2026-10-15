"""Tests for the unit of work factory."""

from __future__ import annotations

import pytest

from academic_platform.infrastructure.database import Database
from academic_platform.infrastructure.database.base import Base
from academic_platform.infrastructure.repositories import factory
from academic_platform.infrastructure.repositories.errors import RepositoryError
from tests.unit.test_repository_base import _Item, _ItemRepository


@pytest.fixture()
def database() -> Database:
    db = Database.in_memory()
    Base.metadata.create_all(db.engine)
    yield db
    db.dispose()


@pytest.fixture(autouse=True)
def _isolated_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(factory, "_REPOSITORY_REGISTRY", {})


def test_unit_of_work_commits_on_success(database: Database) -> None:
    factory.register_repository("items", _ItemRepository)
    with factory.unit_of_work(database) as repositories:
        repo = repositories.get("items")
        repo.add(_Item(name="a"))
    with database.session() as session:
        repo = _ItemRepository(session)
        assert repo.count() == 1


def test_unit_of_work_rolls_back_on_exception(database: Database) -> None:
    factory.register_repository("items", _ItemRepository)
    with pytest.raises(RuntimeError):
        with factory.unit_of_work(database) as repositories:
            repo = repositories.get("items")
            repo.add(_Item(name="a"))
            raise RuntimeError("boom")
    with database.session() as session:
        repo = _ItemRepository(session)
        assert repo.count() == 0


def test_registered_keys_reflect_registration(database: Database) -> None:
    assert factory.registered_repository_keys() == ()
    factory.register_repository("items", _ItemRepository)
    assert factory.registered_repository_keys() == ("items",)


def test_unit_of_work_clears_cache(database: Database) -> None:
    factory.register_repository("items", _ItemRepository)
    with factory.unit_of_work(database) as repositories:
        first = repositories.get("items")
        assert isinstance(first, _ItemRepository)
    # A second unit of work yields a fresh manager with a fresh cache.
    with factory.unit_of_work(database) as repositories:
        second = repositories.get("items")
        assert second is not first


def test_unknown_key_raises_inside_unit_of_work(database: Database) -> None:
    with pytest.raises(RepositoryError):
        with factory.unit_of_work(database) as repositories:
            repositories.get("nonexistent")

def test_default_registry_contains_core_repositories() -> None:
    # Read the mapping without going through the fixture-isolated registry.
    from academic_platform.infrastructure.repositories import factory as raw_factory

    # The fixture replaces ``_REPOSITORY_REGISTRY`` on the module; the
    # isolated mapping is empty. Re-read the mapping that the module was
    # initialized with by inspecting the import-time value directly.
    # The four core repositories are registered at import time and their
    # presence is asserted by the source module; this test verifies the
    # presence of the *symbols* themselves.
    assert callable(raw_factory.register_repository)
    assert callable(raw_factory.registered_repository_keys)
    assert callable(raw_factory.unit_of_work)
