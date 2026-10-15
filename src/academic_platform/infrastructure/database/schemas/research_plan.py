"""Pydantic schemas for the research plan, task, title candidate, methodology proposal, and analysis recommendation models."""

from __future__ import annotations

import datetime as dt

from pydantic import Field, field_validator

from academic_platform.infrastructure.database.schemas._base import PersistenceSchema

_VALID_STATES = {"proposed", "accepted", "rejected", "archived"}


def _validate_state(value: str) -> str:
    if value not in _VALID_STATES:
        raise ValueError(f"state must be one of {sorted(_VALID_STATES)}")
    return value


class ResearchPlanCreate(PersistenceSchema):
    """Payload accepted when creating a research plan."""

    project_id: int = Field(ge=1)
    version_label: str = Field(default="1", max_length=32)
    background: str = ""
    problem_statement: str = ""
    research_question: str = ""
    objectives: str = ""
    design: str = ""
    population: str = ""
    sampling: str = ""
    data_collection: str = ""
    analysis: str = ""
    ethics: str = ""
    limitations: str = ""
    references_text: str = ""
    open_questions: str = ""
    extensions_json: str | None = None


class ResearchPlanUpdate(PersistenceSchema):
    """Payload accepted when updating a research plan."""

    version_label: str | None = Field(default=None, max_length=32)
    background: str | None = None
    problem_statement: str | None = None
    research_question: str | None = None
    objectives: str | None = None
    design: str | None = None
    population: str | None = None
    sampling: str | None = None
    data_collection: str | None = None
    analysis: str | None = None
    ethics: str | None = None
    limitations: str | None = None
    references_text: str | None = None
    open_questions: str | None = None
    extensions_json: str | None = None


class ResearchPlanRead(PersistenceSchema):
    """Payload returned when reading a research plan."""

    id: int
    project_id: int
    version_label: str
    background: str
    problem_statement: str
    research_question: str
    objectives: str
    design: str
    population: str
    sampling: str
    data_collection: str
    analysis: str
    ethics: str
    limitations: str
    references_text: str
    open_questions: str
    extensions_json: str | None
    created_at: dt.datetime
    updated_at: dt.datetime
    version: int


class ResearchTaskCreate(PersistenceSchema):
    """Payload accepted when creating a research task."""

    project_id: int = Field(ge=1)
    title: str = Field(min_length=1, max_length=512)
    description: str = ""
    position: int = Field(default=0, ge=0)
    completed: bool = False
    due_at: dt.datetime | None = None


class ResearchTaskUpdate(PersistenceSchema):
    """Payload accepted when updating a research task."""

    title: str | None = Field(default=None, max_length=512)
    description: str | None = None
    position: int | None = Field(default=None, ge=0)
    completed: bool | None = None
    due_at: dt.datetime | None = None


class ResearchTaskRead(PersistenceSchema):
    """Payload returned when reading a research task."""

    id: int
    project_id: int
    title: str
    description: str
    position: int
    completed: bool
    due_at: dt.datetime | None
    created_at: dt.datetime
    updated_at: dt.datetime
    version: int

    @field_validator("completed", mode="before")
    @classmethod
    def _coerce_int_bool(cls, value: object) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, int):
            return value != 0
        return bool(value)


class ResearchTitleCandidateCreate(PersistenceSchema):
    """Payload accepted when proposing a title."""

    project_id: int = Field(ge=1)
    title: str = Field(min_length=1, max_length=512)
    rationale: str = ""
    strengths: str = ""
    problems: str = ""
    assumptions: str = ""
    state: str = Field(default="proposed", max_length=16)

    @field_validator("state")
    @classmethod
    def _check_state(cls, value: str) -> str:
        return _validate_state(value)


class ResearchTitleCandidateUpdate(PersistenceSchema):
    """Payload accepted when updating a title candidate."""

    title: str | None = Field(default=None, max_length=512)
    rationale: str | None = None
    strengths: str | None = None
    problems: str | None = None
    assumptions: str | None = None
    state: str | None = Field(default=None, max_length=16)

    @field_validator("state")
    @classmethod
    def _check_state(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _validate_state(value)


class ResearchTitleCandidateRead(PersistenceSchema):
    """Payload returned when reading a title candidate."""

    id: int
    project_id: int
    title: str
    rationale: str
    strengths: str
    problems: str
    assumptions: str
    state: str
    created_at: dt.datetime
    updated_at: dt.datetime
    version: int


class MethodologyProposalCreate(PersistenceSchema):
    """Payload accepted when proposing a methodology."""

    project_id: int = Field(ge=1)
    methodology_key: str = Field(min_length=1, max_length=64)
    display_name: str = Field(default="", max_length=255)
    rationale: str = ""
    strengths: str = ""
    limitations: str = ""
    assumptions: str = ""
    data_requirements: str = ""
    ethical_notes: str = ""
    state: str = Field(default="proposed", max_length=16)

    @field_validator("state")
    @classmethod
    def _check_state(cls, value: str) -> str:
        return _validate_state(value)


class MethodologyProposalUpdate(PersistenceSchema):
    """Payload accepted when updating a methodology proposal."""

    display_name: str | None = Field(default=None, max_length=255)
    rationale: str | None = None
    strengths: str | None = None
    limitations: str | None = None
    assumptions: str | None = None
    data_requirements: str | None = None
    ethical_notes: str | None = None
    state: str | None = Field(default=None, max_length=16)

    @field_validator("state")
    @classmethod
    def _check_state(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _validate_state(value)


class MethodologyProposalRead(PersistenceSchema):
    """Payload returned when reading a methodology proposal."""

    id: int
    project_id: int
    methodology_key: str
    display_name: str
    rationale: str
    strengths: str
    limitations: str
    assumptions: str
    data_requirements: str
    ethical_notes: str
    state: str
    created_at: dt.datetime
    updated_at: dt.datetime
    version: int


class AnalysisRecommendationCreate(PersistenceSchema):
    """Payload accepted when creating an analysis recommendation."""

    project_id: int = Field(ge=1)
    method_key: str = Field(min_length=1, max_length=64)
    display_name: str = Field(default="", max_length=255)
    rationale: str = ""
    assumptions: str = ""
    diagnostics: str = ""
    alternatives: str = ""
    cautions: str = ""
    state: str = Field(default="proposed", max_length=16)

    @field_validator("state")
    @classmethod
    def _check_state(cls, value: str) -> str:
        return _validate_state(value)


class AnalysisRecommendationUpdate(PersistenceSchema):
    """Payload accepted when updating an analysis recommendation."""

    display_name: str | None = Field(default=None, max_length=255)
    rationale: str | None = None
    assumptions: str | None = None
    diagnostics: str | None = None
    alternatives: str | None = None
    cautions: str | None = None
    state: str | None = Field(default=None, max_length=16)

    @field_validator("state")
    @classmethod
    def _check_state(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _validate_state(value)


class AnalysisRecommendationRead(PersistenceSchema):
    """Payload returned when reading an analysis recommendation."""

    id: int
    project_id: int
    method_key: str
    display_name: str
    rationale: str
    assumptions: str
    diagnostics: str
    alternatives: str
    cautions: str
    state: str
    created_at: dt.datetime
    updated_at: dt.datetime
    version: int