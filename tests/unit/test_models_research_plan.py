"""Tests for the research plan and proposal models."""

from __future__ import annotations

import pytest

from academic_platform.infrastructure.database import DatabaseError

from academic_platform.infrastructure.database import Database
from academic_platform.infrastructure.database.base import Base
from academic_platform.infrastructure.database.models import (
    AnalysisRecommendation,
    MethodologyProposal,
    ResearchPlan,
    ResearchProject,
    ResearchTask,
    ResearchTitleCandidate,
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


def test_plan_and_task(database: Database) -> None:
    project_id = _seed_project(database)
    with database.session() as session:
        plan = ResearchPlan(project_id=project_id, version_label="1")
        session.add(plan)
        session.flush()
        session.add(
            ResearchTask(project_id=project_id, title="Read papers", position=0)
        )
    with database.session() as session:
        assert session.query(ResearchPlan).count() == 1
        assert session.query(ResearchTask).count() == 1


def test_title_candidate_state(database: Database) -> None:
    project_id = _seed_project(database)
    with database.session() as session:
        session.add(
            ResearchTitleCandidate(
                project_id=project_id,
                title="A title",
                state="accepted",
            )
        )
    with database.session() as session:
        candidate = session.query(ResearchTitleCandidate).one()
        assert candidate.state == "accepted"


def test_title_candidate_invalid_state(database: Database) -> None:
    project_id = _seed_project(database)
    with pytest.raises(DatabaseError):
        with database.session() as session:
            session.add(
                ResearchTitleCandidate(
                    project_id=project_id,
                    title="A title",
                    state="bogus",
                )
            )


def test_methodology_and_analysis_recommendation(database: Database) -> None:
    project_id = _seed_project(database)
    with database.session() as session:
        session.add(
            MethodologyProposal(
                project_id=project_id,
                methodology_key="cross_sectional",
            )
        )
        session.add(
            AnalysisRecommendation(
                project_id=project_id,
                method_key="t_test",
            )
        )
    with database.session() as session:
        assert session.query(MethodologyProposal).count() == 1
        assert session.query(AnalysisRecommendation).count() == 1


def test_cascade_delete_from_project(database: Database) -> None:
    project_id = _seed_project(database)
    with database.session() as session:
        session.add(
            ResearchPlan(project_id=project_id, version_label="1")
        )
        session.add(
            ResearchTask(project_id=project_id, title="Task")
        )
        session.add(
            ResearchTitleCandidate(project_id=project_id, title="Title")
        )
        session.add(
            MethodologyProposal(project_id=project_id, methodology_key="m")
        )
        session.add(
            AnalysisRecommendation(project_id=project_id, method_key="a")
        )
    with database.session() as session:
        project = session.get(ResearchProject, project_id)
        assert project is not None
        session.delete(project)
    with database.session() as session:
        for model in (
            ResearchPlan,
            ResearchTask,
            ResearchTitleCandidate,
            MethodologyProposal,
            AnalysisRecommendation,
        ):
            assert session.query(model).count() == 0, model