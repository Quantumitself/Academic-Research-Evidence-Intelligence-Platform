"""Tests for the research plan repositories."""

from __future__ import annotations

import pytest

from academic_platform.infrastructure.database import Database
from academic_platform.infrastructure.database.base import Base
from academic_platform.infrastructure.database.models import ResearchProject
from academic_platform.infrastructure.database.schemas import (
    AnalysisRecommendationCreate,
    MethodologyProposalCreate,
    ResearchPlanCreate,
    ResearchTaskCreate,
    ResearchTitleCandidateCreate,
)
from academic_platform.infrastructure.repositories.research_plan_repository import (
    AnalysisRecommendationRepository,
    MethodologyProposalRepository,
    ResearchPlanRepository,
    ResearchTaskRepository,
    ResearchTitleCandidateRepository,
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


def test_plan_latest(database: Database) -> None:
    project_id = _seed_project(database)
    with database.session() as session:
        repo = ResearchPlanRepository(session)
        repo.create(ResearchPlanCreate(project_id=project_id, version_label="1"))
        repo.create(ResearchPlanCreate(project_id=project_id, version_label="2"))
    with database.session() as session:
        repo = ResearchPlanRepository(session)
        latest = repo.latest_for_project(project_id)
        assert latest is not None
        assert latest.version_label == "2"


def test_task_completion_and_open_list(database: Database) -> None:
    project_id = _seed_project(database)
    with database.session() as session:
        repo = ResearchTaskRepository(session)
        repo.create(ResearchTaskCreate(project_id=project_id, title="A"))
        repo.create(ResearchTaskCreate(project_id=project_id, title="B"))
    with database.session() as session:
        repo = ResearchTaskRepository(session)
        assert len(repo.list_open_for_project(project_id)) == 2
        repo.set_completed(1, True)
    with database.session() as session:
        repo = ResearchTaskRepository(session)
        assert len(repo.list_open_for_project(project_id)) == 1


def test_title_candidate_set_state(database: Database) -> None:
    project_id = _seed_project(database)
    with database.session() as session:
        repo = ResearchTitleCandidateRepository(session)
        candidate = repo.create(
            ResearchTitleCandidateCreate(project_id=project_id, title="T")
        )
        candidate_id = candidate.id
    with database.session() as session:
        repo = ResearchTitleCandidateRepository(session)
        updated = repo.set_state(candidate_id, "accepted")
        assert updated.state == "accepted"


def test_methodology_set_state(database: Database) -> None:
    project_id = _seed_project(database)
    with database.session() as session:
        repo = MethodologyProposalRepository(session)
        proposal = repo.create(
            MethodologyProposalCreate(project_id=project_id, methodology_key="m")
        )
        proposal_id = proposal.id
    with database.session() as session:
        repo = MethodologyProposalRepository(session)
        updated = repo.set_state(proposal_id, "rejected")
        assert updated.state == "rejected"


def test_analysis_recommendation_set_state(database: Database) -> None:
    project_id = _seed_project(database)
    with database.session() as session:
        repo = AnalysisRecommendationRepository(session)
        recommendation = repo.create(
            AnalysisRecommendationCreate(project_id=project_id, method_key="a")
        )
        recommendation_id = recommendation.id
    with database.session() as session:
        repo = AnalysisRecommendationRepository(session)
        updated = repo.set_state(recommendation_id, "accepted")
        assert updated.state == "accepted"