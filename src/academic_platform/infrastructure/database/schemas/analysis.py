"""Pydantic schemas for the analysis run, input, and result models."""

from __future__ import annotations

import datetime as dt

from pydantic import Field, field_validator

from academic_platform.infrastructure.database.schemas._base import PersistenceSchema

_VALID_STATUSES = {"running", "succeeded", "failed", "cancelled"}
_VALID_ANALYSIS_TYPES = {
    "descriptive",
    "t_test",
    "correlation",
    "regression",
    "effect_size",
    "meta_analysis",
    "reliability",
    "other",
}
_VALID_VALUE_KINDS = {"number", "integer", "string", "boolean", "list", "null"}


class AnalysisRunCreate(PersistenceSchema):
    """Payload accepted when recording an analysis run."""

    analysis_type: str = Field(max_length=32)
    status: str = Field(max_length=16)
    started_at: dt.datetime
    finished_at: dt.datetime | None = None
    duration_ms: int | None = Field(default=None, ge=0)
    engine_version: int = Field(default=1, ge=1)
    library_versions_json: str | None = None
    settings_json: str | None = None
    warnings_json: str | None = None
    result_json: str | None = None
    error_message: str | None = None
    inputs_count: int = Field(default=0, ge=0)

    @field_validator("status")
    @classmethod
    def _check_status(cls, value: str) -> str:
        if value not in _VALID_STATUSES:
            raise ValueError(
                f"status must be one of {sorted(_VALID_STATUSES)}"
            )
        return value

    @field_validator("analysis_type")
    @classmethod
    def _check_analysis_type(cls, value: str) -> str:
        if value not in _VALID_ANALYSIS_TYPES:
            raise ValueError(
                f"analysis_type must be one of {sorted(_VALID_ANALYSIS_TYPES)}"
            )
        return value


class AnalysisRunRead(PersistenceSchema):
    """Payload returned when reading an analysis run."""

    id: int
    analysis_type: str
    status: str
    started_at: dt.datetime
    finished_at: dt.datetime | None
    duration_ms: int | None
    engine_version: int
    library_versions_json: str | None
    settings_json: str | None
    warnings_json: str | None
    result_json: str | None
    error_message: str | None
    inputs_count: int
    created_at: dt.datetime
    updated_at: dt.datetime


class AnalysisInputCreate(PersistenceSchema):
    """Payload accepted when recording an analysis input."""

    analysis_run_id: int = Field(ge=1)
    input_key: str = Field(min_length=1, max_length=128)
    value_kind: str = Field(max_length=32)
    value_text: str | None = None
    source_evidence_id: int | None = Field(default=None, ge=1)

    @field_validator("value_kind")
    @classmethod
    def _check_value_kind(cls, value: str) -> str:
        if value not in _VALID_VALUE_KINDS:
            raise ValueError(
                f"value_kind must be one of {sorted(_VALID_VALUE_KINDS)}"
            )
        return value


class AnalysisInputRead(PersistenceSchema):
    """Payload returned when reading an analysis input."""

    id: int
    analysis_run_id: int
    input_key: str
    value_kind: str
    value_text: str | None
    source_evidence_id: int | None
    created_at: dt.datetime
    updated_at: dt.datetime