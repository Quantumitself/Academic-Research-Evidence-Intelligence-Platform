"""Tests for the ResearchQuestion model."""

from __future__ import annotations

import pytest

from academic_platform.infrastructure.database import DatabaseError

from academic_platform.infrastructure.database import Database
from academic_platform.infrastructure.database.base import Base
from academic_platform.infrastructure.database.models import (
    ResearchProject,
    ResearchQuestion,
)


@pytest.fixture()
def database() -> Database:
    db = Database.in_memory()
    Base.metadata.create_all(db.engine)
    yield db
    db.dispose()


def test_create_and_read(database: Database) -> None:
    with database.session() as session:
        project = ResearchProject(key="p1")
        session.add(project)
        session.flush()
        question = ResearchQuestion(project_id=project.id, text="Why?")
        session.add(question)
        session.flush()
        identifier = question.id
    with database.session() as session:
        loaded = session.get(ResearchQuestion, identifier)
        assert loaded is not None
        assert loaded.text == "Why?"
        assert loaded.kind == "main"
        assert loaded.is_primary == 0


def test_invalid_kind_rejected(database: Database) -> None:
    with pytest.raises(DatabaseError):
        with database.session() as session:
            project = ResearchProject(key="p1")
            session.add(project)
            session.flush()
            session.add(
                ResearchQuestion(project_id=project.id, text="x", kind="bogus")
            )


def test_cascade_delete_removes_questions(database: Database) -> None:
    with database.session() as session:
        project = ResearchProject(key="p1")
        session.add(project)
        session.flush()
        session.add(ResearchQuestion(project_id=project.id, text="q"))
    with database.session() as session:
        project = session.get(ResearchProject, 1)
        assert project is not None
        session.delete(project)
    with database.session() as session:
        remaining = session.query(ResearchQuestion).count()
        assert remaining == 0