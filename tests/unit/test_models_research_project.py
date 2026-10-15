"""Tests for the ResearchProject model."""

from __future__ import annotations

import pytest

from academic_platform.infrastructure.database import DatabaseError

from academic_platform.infrastructure.database import Database
from academic_platform.infrastructure.database.base import Base
from academic_platform.infrastructure.database.models import ResearchProject


@pytest.fixture()
def database() -> Database:
    db = Database.in_memory()
    Base.metadata.create_all(db.engine)
    yield db
    db.dispose()


def test_create_and_read(database: Database) -> None:
    with database.session() as session:
        project = ResearchProject(key="p1", title="Project A", topic="Topic")
        session.add(project)
        session.flush()
        identifier = project.id
    with database.session() as session:
        loaded = session.get(ResearchProject, identifier)
        assert loaded is not None
        assert loaded.key == "p1"
        assert loaded.stage == "idea"
        assert loaded.version == 1


def test_key_unique(database: Database) -> None:
    with database.session() as session:
        session.add(ResearchProject(key="p1"))
    with pytest.raises(DatabaseError):
        with database.session() as session:
            session.add(ResearchProject(key="p1"))


def test_invalid_stage_rejected(database: Database) -> None:
    with pytest.raises(DatabaseError):
        with database.session() as session:
            session.add(ResearchProject(key="p1", stage="bogus"))


def test_metadata_round_trip(database: Database) -> None:
    with database.session() as session:
        project = ResearchProject(
            key="p1",
            project_metadata='{"notes": "hello"}',
        )
        session.add(project)
        session.flush()
        identifier = project.id
    with database.session() as session:
        loaded = session.get(ResearchProject, identifier)
        assert loaded is not None
        assert loaded.project_metadata == '{"notes": "hello"}'