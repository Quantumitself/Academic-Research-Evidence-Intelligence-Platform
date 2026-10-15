"""Tests for the declarative base and mixins."""

from __future__ import annotations

import datetime as dt
import time

import pytest
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from academic_platform.infrastructure.database import Database
from academic_platform.infrastructure.database.base import (
    Base,
    TimestampMixin,
    VersionMixin,
)


class _Sample(Base, TimestampMixin, VersionMixin):
    __tablename__ = "sample_base_test"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(32), nullable=False)


@pytest.fixture()
def database() -> Database:
    db = Database.in_memory()
    Base.metadata.create_all(db.engine)
    yield db
    db.dispose()


def test_metadata_naming_convention_applied() -> None:
    pk = next(iter(_Sample.__table__.primary_key.columns))
    assert pk.name == "id"
    assert "sample_base_test" in Base.metadata.tables


def test_timestamp_mixin_populates_on_insert(database: Database) -> None:
    with database.session() as session:
        row = _Sample(name="a")
        session.add(row)
        session.flush()
        created = row.created_at
        updated = row.updated_at
    assert isinstance(created, dt.datetime)
    assert isinstance(updated, dt.datetime)
    assert created.tzinfo is None


def test_timestamp_mixin_updates_on_update(database: Database) -> None:
    with database.session() as session:
        row = _Sample(name="a")
        session.add(row)
        session.flush()
        first_updated = row.updated_at
    time.sleep(0.01)
    with database.session() as session:
        loaded = session.get(_Sample, row.id)
        assert loaded is not None
        loaded.name = "b"
        session.flush()
        second_updated = loaded.updated_at
    assert second_updated >= first_updated


def test_version_mixin_defaults_to_one(database: Database) -> None:
    with database.session() as session:
        row = _Sample(name="a")
        session.add(row)
        session.flush()
    assert row.version == 1


def test_to_dict_includes_columns(database: Database) -> None:
    with database.session() as session:
        row = _Sample(name="a")
        session.add(row)
        session.flush()
        data = row.to_dict()
    assert data["name"] == "a"
    assert "created_at" in data
    assert "updated_at" in data
    assert "version" in data