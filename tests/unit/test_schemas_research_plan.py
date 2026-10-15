"""Tests for the research plan Pydantic schemas."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from academic_platform.infrastructure.database.schemas import (
    AnalysisRecommendationCreate,
    MethodologyProposalCreate,
    ResearchPlanCreate,
    ResearchTaskCreate,
    ResearchTitleCandidateCreate,
)


def test_plan_create_defaults() -> None:
    payload = ResearchPlanCreate(project_id=1)
    assert payload.version_label == "1"
    assert payload.extensions_json is None


def test_task_create_defaults() -> None:
    payload = ResearchTaskCreate(project_id=1, title="Read")
    assert payload.completed is False


def test_title_candidate_create_defaults() -> None:
    payload = ResearchTitleCandidateCreate(project_id=1, title="T")
    assert payload.state == "proposed"


def test_title_candidate_rejects_bad_state() -> None:
    with pytest.raises(ValidationError):
        ResearchTitleCandidateCreate(
            project_id=1, title="T", state="bogus"
        )


def test_methodology_proposal_create_defaults() -> None:
    payload = MethodologyProposalCreate(project_id=1, methodology_key="m")
    assert payload.state == "proposed"


def test_analysis_recommendation_create_defaults() -> None:
    payload = AnalysisRecommendationCreate(project_id=1, method_key="a")
    assert payload.state == "proposed"