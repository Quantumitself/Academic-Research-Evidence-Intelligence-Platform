"""Tests for the ResearchProjectRepository."""

from __future__ import annotations

import pytest

from academic_platform.infrastructure.database import Database
from academic_platform.infrastructure.database.base import Base
from academic_platform.infrastructure.database.models import ResearchProject
from academic_platform.infrastructure.database.schemas import (
    ResearchProjectCreate,
    ResearchProjectUpdate,
)
from academic_platform.infrastructure.repositories.research_project_repository import (
    ResearchProjectRepository,
)


@pytest.fixture()
def database() -> Database:
    db = Database.in_memory()
    Base.metadata.create_all(db.engine)
    yield db
    db.dispose()


def test_create_from_schema(database: Database) -> None:
    with database.session() as session:
        repo = ResearchProjectRepository(session)
        project = repo.create(ResearchProjectCreate(key="p1", title="A"))
        assert project.title == "A"


def test_find_by_key(database: Database) -> None:
    with database.session() as session:
        repo = ResearchProjectRepository(session)
        repo.add(ResearchProject(key="p1", title="A"))
    with database.session() as session:
        repo = ResearchProjectRepository(session)
        found = repo.find_by_key("p1")
        assert found is not None
        assert found.title == "A"
        assert repo.find_by_key("missing") is None


def test_update(database: Database) -> None:
    with database.session() as session:
        repo = ResearchProjectRepository(session)
        project = repo.add(ResearchProject(key="p1", title="A"))
    with database.session() as session:
        repo = ResearchProjectRepository(session)
        loaded = repo.get_or_raise(project.id)
        repo.update(loaded, ResearchProjectUpdate(stage="design"))
        assert loaded.stage == "design"
        assert loaded.title == "A"


def test_list_ordered_by_updated(database: Database) -> None:
    with database.session() as session:
        repo = ResearchProjectRepository(session)
        repo.add(ResearchProject(key="a", title="A"))
        repo.add(ResearchProject(key="b", title="B"))
    with database.session() as session:
        repo = ResearchProjectRepository(session)
        ordered = repo.list_ordered_by_updated()
        assert {p.key for p in ordered} == {"a", "b"}


def test_list_ordered_by_updated_limit(database: Database) -> None:
    with database.session() as session:
        repo = ResearchProjectRepository(session)
        for index in range(5):
            repo.add(ResearchProject(key=f"p{index}"))
    with database.session() as session:
        repo = ResearchProjectRepository(session)
        assert len(repo.list_ordered_by_updated(limit=2)) == 2


def test_question_count(database: Database) -> None:
    from academic_platform.infrastructure.database.models import ResearchQuestion

    with database.session() as session:
        repo = ResearchProjectRepository(session)
        project = repo.add(ResearchProject(key="p1"))
        session.add(ResearchQuestion(project_id=project.id, text="q1"))
        session.add(ResearchQuestion(project_id=project.id, text="q2"))
    with database.session() as session:
        repo = ResearchProjectRepository(session)
        assert repo.question_count(project.id) == 2