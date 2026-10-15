"""Tests for the AppSettings model."""

from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError

from academic_platform.infrastructure.database import Database
from academic_platform.infrastructure.database.base import Base
from academic_platform.infrastructure.database.models import AppSettings


@pytest.fixture()
def database() -> Database:
    db = Database.in_memory()
    Base.metadata.create_all(db.engine)
    yield db
    db.dispose()


def test_singleton_insert(database: Database) -> None:
    with database.session() as session:
        session.add(AppSettings(id=1, active_user_key="alice"))
    with database.session() as session:
        loaded = session.get(AppSettings, 1)
        assert loaded is not None
        assert loaded.active_user_key == "alice"
        assert loaded.settings_schema_version == 1


def test_single_row_constraint(database: Database) -> None:
    from academic_platform.infrastructure.database import DatabaseError

    with database.session() as session:
        session.add(AppSettings(id=1))
    with pytest.raises(DatabaseError):
        with database.session() as session:
            session.add(AppSettings(id=2))