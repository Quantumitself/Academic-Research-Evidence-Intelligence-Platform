"""Tests for the ResearchQuestionRepository."""

from __future__ import annotations

import pytest

from academic_platform.infrastructure.database import Database
from academic_platform.infrastructure.database.base import Base
from academic_platform.infrastructure.database.models import (
    ResearchProject,
    ResearchQuestion,
)
from academic_platform.infrastructure.repositories.research_question_repository import (
    ResearchQuestionRepository,
)


@pytest.fixture()
def database() -> Database:
    db = Database.in_memory()
    Base.metadata.create_all(db.engine)
    yield db
    db.dispose()


def _seed_project(database: Database) -> int:
    with database.session() as session:
        project = ResearchProject(key="p1")
        session.add(project)
        session.flush()
        return project.id


def test_list_for_project_orders_by_position(database: Database) -> None:
    project_id = _seed_project(database)
    with database.session() as session:
        repo = ResearchQuestionRepository(session)
        repo.add_all(
            [
                ResearchQuestion(project_id=project_id, text="c", position=2),
                ResearchQuestion(project_id=project_id, text="a", position=0),
                ResearchQuestion(project_id=project_id, text="b", position=1),
            ]
        )
    with database.session() as session:
        repo = ResearchQuestionRepository(session)
        ordered = [q.text for q in repo.list_for_project(project_id)]
        assert ordered == ["a", "b", "c"]


def test_primary_for_project(database: Database) -> None:
    project_id = _seed_project(database)
    with database.session() as session:
        repo = ResearchQuestionRepository(session)
        repo.add(ResearchQuestion(project_id=project_id, text="a"))
        repo.add(ResearchQuestion(project_id=project_id, text="b", is_primary=1))
    with database.session() as session:
        repo = ResearchQuestionRepository(session)
        primary = repo.primary_for_project(project_id)
        assert primary is not None
        assert primary.text == "b"


def test_clear_primary(database: Database) -> None:
    project_id = _seed_project(database)
    with database.session() as session:
        repo = ResearchQuestionRepository(session)
        repo.add(ResearchQuestion(project_id=project_id, text="a", is_primary=1))
        repo.add(ResearchQuestion(project_id=project_id, text="b", is_primary=1))
    with database.session() as session:
        repo = ResearchQuestionRepository(session)
        updated = repo.clear_primary_for_project(project_id)
        assert updated == 2
        assert repo.primary_for_project(project_id) is None


def test_next_position(database: Database) -> None:
    project_id = _seed_project(database)
    with database.session() as session:
        repo = ResearchQuestionRepository(session)
        assert repo.next_position(project_id) == 1
        repo.add(ResearchQuestion(project_id=project_id, text="a", position=5))
    with database.session() as session:
        repo = ResearchQuestionRepository(session)
        assert repo.next_position(project_id) == 6