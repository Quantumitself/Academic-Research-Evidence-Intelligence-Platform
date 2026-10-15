"""Tests for the specification combinators."""

from __future__ import annotations

from sqlalchemy import String, select
from sqlalchemy.orm import Mapped, mapped_column

from academic_platform.infrastructure.database import Database
from academic_platform.infrastructure.database.base import Base
from academic_platform.infrastructure.repositories.specification import (
    AndSpecification,
    NotSpecification,
    OrSpecification,
    Specification,
)


class _Row(Base):
    __tablename__ = "spec_test_row"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(32), nullable=False)
    flag: Mapped[int] = mapped_column(nullable=False, default=0)


class _NameEquals(Specification[_Row]):
    def __init__(self, name: str) -> None:
        self._name = name

    def to_expression(self, entity):
        return entity.name == self._name


class _FlagSet(Specification[_Row]):
    def to_expression(self, entity):
        return entity.flag == 1


def _seed(database: Database) -> None:
    Base.metadata.create_all(database.engine)
    with database.session() as session:
        session.add_all(
            [
                _Row(name="a", flag=0),
                _Row(name="b", flag=1),
                _Row(name="c", flag=1),
            ]
        )


def test_single_specification_matches() -> None:
    database = Database.in_memory()
    try:
        _seed(database)
        with database.session() as session:
            rows = session.execute(
                select(_Row).where(_NameEquals("b").to_expression(_Row))
            ).scalars().all()
        assert [row.name for row in rows] == ["b"]
    finally:
        database.dispose()


def test_and_specification() -> None:
    database = Database.in_memory()
    try:
        _seed(database)
        spec = _FlagSet() & _NameEquals("c")
        assert isinstance(spec, AndSpecification)
        with database.session() as session:
            rows = session.execute(select(_Row).where(spec.to_expression(_Row))).scalars().all()
        assert [row.name for row in rows] == ["c"]
    finally:
        database.dispose()


def test_or_specification() -> None:
    database = Database.in_memory()
    try:
        _seed(database)
        spec = _NameEquals("a") | _NameEquals("b")
        assert isinstance(spec, OrSpecification)
        with database.session() as session:
            rows = session.execute(
                select(_Row).where(spec.to_expression(_Row)).order_by(_Row.name)
            ).scalars().all()
        assert [row.name for row in rows] == ["a", "b"]
    finally:
        database.dispose()


def test_not_specification() -> None:
    database = Database.in_memory()
    try:
        _seed(database)
        spec = ~_NameEquals("a")
        assert isinstance(spec, NotSpecification)
        with database.session() as session:
            rows = session.execute(
                select(_Row).where(spec.to_expression(_Row)).order_by(_Row.name)
            ).scalars().all()
        assert [row.name for row in rows] == ["b", "c"]
    finally:
        database.dispose()