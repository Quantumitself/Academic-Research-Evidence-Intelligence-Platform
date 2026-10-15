"""Tests for the base repository."""

from __future__ import annotations

import pytest
from pydantic import BaseModel
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from academic_platform.infrastructure.database import Database
from academic_platform.infrastructure.database.base import Base, TimestampMixin
from academic_platform.infrastructure.repositories.base import Repository
from academic_platform.infrastructure.repositories.errors import (
    DuplicateEntityError,
    EntityNotFoundError,
    RepositoryValidationError,
)
from academic_platform.infrastructure.repositories.pagination import PageRequest
from academic_platform.infrastructure.repositories.specification import Specification


class _Item(Base, TimestampMixin):
    __tablename__ = "repo_test_item"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    value: Mapped[int] = mapped_column(nullable=False, default=0)


class _CreatePayload(BaseModel):
    name: str
    value: int = 0


class _UpdatePayload(BaseModel):
    name: str | None = None
    value: int | None = None


class _ItemRepository(Repository[_Item]):
    entity = _Item


class _NameEquals(Specification[_Item]):
    def __init__(self, name: str) -> None:
        self._name = name

    def to_expression(self, entity):
        return entity.name == self._name


@pytest.fixture()
def database() -> Database:
    db = Database.in_memory()
    Base.metadata.create_all(db.engine)
    yield db
    db.dispose()


def test_repository_requires_entity_attribute() -> None:
    class _Bad(Repository):
        pass

    with pytest.raises(Exception):
        _Bad(None)  # type: ignore[arg-type]


def test_add_and_get(database: Database) -> None:
    with database.session() as session:
        repo = _ItemRepository(session)
        item = repo.add(_Item(name="a", value=1))
        identifier = item.id
    with database.session() as session:
        repo = _ItemRepository(session)
        loaded = repo.get(identifier)
        assert loaded is not None
        assert loaded.name == "a"


def test_get_or_raise_on_missing(database: Database) -> None:
    with database.session() as session:
        repo = _ItemRepository(session)
        with pytest.raises(EntityNotFoundError):
            repo.get_or_raise(999)


def test_create_from_pydantic(database: Database) -> None:
    with database.session() as session:
        repo = _ItemRepository(session)
        item = repo.create(_CreatePayload(name="a", value=5))
        assert item.name == "a"
        assert item.value == 5


def test_create_requires_pydantic(database: Database) -> None:
    with database.session() as session:
        repo = _ItemRepository(session)
        with pytest.raises(RepositoryValidationError):
            repo.create({"name": "a"})  # type: ignore[arg-type]


def test_create_translates_integrity_error(database: Database) -> None:
    with database.session() as session:
        repo = _ItemRepository(session)
        repo.create(_CreatePayload(name="a"))
    with pytest.raises(DuplicateEntityError):
        with database.session() as session:
            repo = _ItemRepository(session)
            repo.create(_CreatePayload(name="a"))


def test_update_applies_only_set_fields(database: Database) -> None:
    with database.session() as session:
        repo = _ItemRepository(session)
        item = repo.add(_Item(name="a", value=1))
    with database.session() as session:
        repo = _ItemRepository(session)
        loaded = repo.get_or_raise(item.id)
        repo.update(loaded, _UpdatePayload(value=9))
        assert loaded.value == 9
        assert loaded.name == "a"


def test_update_rejects_unknown_field(database: Database) -> None:
    class _Bogus(BaseModel):
        nonexistent: str | None = None

    with database.session() as session:
        repo = _ItemRepository(session)
        item = repo.add(_Item(name="a"))
        with pytest.raises(RepositoryValidationError):
            repo.update(item, _Bogus(nonexistent="x"))


def test_delete(database: Database) -> None:
    with database.session() as session:
        repo = _ItemRepository(session)
        item = repo.add(_Item(name="a"))
        identifier = item.id
    with database.session() as session:
        repo = _ItemRepository(session)
        repo.delete(repo.get_or_raise(identifier))
    with database.session() as session:
        repo = _ItemRepository(session)
        assert repo.get(identifier) is None


def test_delete_by_id_returns_flag(database: Database) -> None:
    with database.session() as session:
        repo = _ItemRepository(session)
        item = repo.add(_Item(name="a"))
        identifier = item.id
    with database.session() as session:
        repo = _ItemRepository(session)
        assert repo.delete_by_id(identifier) is True
        assert repo.delete_by_id(identifier) is False


def test_update_fields(database: Database) -> None:
    with database.session() as session:
        repo = _ItemRepository(session)
        item = repo.add(_Item(name="a", value=1))
        identifier = item.id
    with database.session() as session:
        repo = _ItemRepository(session)
        updated = repo.update_fields(identifier, value=42)
        assert updated.value == 42


def test_update_fields_missing_raises(database: Database) -> None:
    with pytest.raises(EntityNotFoundError):
        with database.session() as session:
            repo = _ItemRepository(session)
            repo.update_fields(999, value=1)


def test_find_all_with_specification(database: Database) -> None:
    with database.session() as session:
        repo = _ItemRepository(session)
        repo.add_all([_Item(name="a"), _Item(name="b")])
    with database.session() as session:
        repo = _ItemRepository(session)
        found = repo.find_all(_NameEquals("b"))
        assert len(found) == 1
        assert found[0].name == "b"


def test_find_all_orders_and_limits(database: Database) -> None:
    with database.session() as session:
        repo = _ItemRepository(session)
        repo.add_all([_Item(name=c) for c in "cba"])
    with database.session() as session:
        repo = _ItemRepository(session)
        found = repo.find_all(order_by=[_Item.name], limit=2)
        assert [item.name for item in found] == ["a", "b"]


def test_find_one(database: Database) -> None:
    with database.session() as session:
        repo = _ItemRepository(session)
        repo.add(_Item(name="a"))
    with database.session() as session:
        repo = _ItemRepository(session)
        found = repo.find_one(_NameEquals("a"))
        assert found is not None
        assert repo.find_one(_NameEquals("zzz")) is None


def test_count_and_exists(database: Database) -> None:
    with database.session() as session:
        repo = _ItemRepository(session)
        repo.add_all([_Item(name="a"), _Item(name="b")])
    with database.session() as session:
        repo = _ItemRepository(session)
        assert repo.count() == 2
        assert repo.count(_NameEquals("a")) == 1
        assert repo.exists(_NameEquals("a")) is True
        assert repo.exists(_NameEquals("zzz")) is False


def test_find_page(database: Database) -> None:
    with database.session() as session:
        repo = _ItemRepository(session)
        repo.add_all([_Item(name=f"item-{i:02d}") for i in range(25)])
    with database.session() as session:
        repo = _ItemRepository(session)
        page = repo.find_page(PageRequest(page=2, size=10), order_by=[_Item.name])
        assert page.total == 25
        assert len(page.items) == 10
        assert page.items[0].name == "item-10"
        assert page.has_next
        assert page.has_previous


def test_add_all(database: Database) -> None:
    with database.session() as session:
        repo = _ItemRepository(session)
        items = repo.add_all([_Item(name="a"), _Item(name="b")])
        assert len(items) == 2
        assert all(item.id is not None for item in items)