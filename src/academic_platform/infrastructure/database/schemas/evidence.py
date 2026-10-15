"""Pydantic schemas for the evidence record and extraction run models."""

from __future__ import annotations

import datetime as dt

from pydantic import Field, field_validator

from academic_platform.infrastructure.database.schemas._base import PersistenceSchema

_VALID_EVIDENCE_TYPES = {
    "study_design",
    "population",
    "sample_size",
    "measurement",
    "group_statistic",
    "effect_estimate",
    "p_value",
    "confidence_interval",
    "covariate",
    "limitation",
    "outcome_definition",
    "other",
}
_VALID_VERIFICATION_STATES = {
    "ai_proposed",
    "auto_parsed",
    "user_verified",
    "uncertain",
    "rejected",
    "missing",
}
_VALID_EXTRACTION_METHODS = {"rule_based", "ai_assisted", "user_entered"}
_VALID_RUN_STATUSES = {"running", "succeeded", "failed", "cancelled"}
_VALID_RUN_METHODS = {"rule_based", "ai_assisted", "hybrid"}


def _validate_evidence_type(value: str) -> str:
    if value not in _VALID_EVIDENCE_TYPES:
        raise ValueError(
            f"evidence_type must be one of {sorted(_VALID_EVIDENCE_TYPES)}"
        )
    return value


def _validate_verification(value: str) -> str:
    if value not in _VALID_VERIFICATION_STATES:
        raise ValueError(
            f"verification_status must be one of {sorted(_VALID_VERIFICATION_STATES)}"
        )
    return value


def _validate_method(value: str) -> str:
    if value not in _VALID_EXTRACTION_METHODS:
        raise ValueError(
            f"extraction_method must be one of {sorted(_VALID_EXTRACTION_METHODS)}"
        )
    return value


class EvidenceRecordCreate(PersistenceSchema):
    """Payload accepted when creating an evidence record."""

    document_id: int = Field(ge=1)
    extraction_run_id: int | None = Field(default=None, ge=1)
    evidence_type: str = Field(max_length=32)
    field_key: str = Field(default="", max_length=64)
    reported_value_json: str | None = None
    normalized_value_json: str | None = None
    units: str | None = Field(default=None, max_length=64)
    raw_source_text: str | None = None
    page_number: int | None = Field(default=None, ge=1)
    section_title: str | None = Field(default=None, max_length=512)
    table_reference: str | None = Field(default=None, max_length=64)
    figure_reference: str | None = Field(default=None, max_length=64)
    extraction_method: str = Field(default="rule_based", max_length=32)
    verification_status: str = Field(default="ai_proposed", max_length=32)
    notes: str = ""
    user_correction_json: str | None = None

    @field_validator("evidence_type")
    @classmethod
    def _check_type(cls, value: str) -> str:
        return _validate_evidence_type(value)

    @field_validator("extraction_method")
    @classmethod
    def _check_method(cls, value: str) -> str:
        return _validate_method(value)

    @field_validator("verification_status")
    @classmethod
    def _check_verification(cls, value: str) -> str:
        return _validate_verification(value)


class EvidenceRecordUpdate(PersistenceSchema):
    """Payload accepted when updating an evidence record."""

    reported_value_json: str | None = None
    normalized_value_json: str | None = None
    units: str | None = Field(default=None, max_length=64)
    raw_source_text: str | None = None
    page_number: int | None = Field(default=None, ge=1)
    section_title: str | None = Field(default=None, max_length=512)
    table_reference: str | None = Field(default=None, max_length=64)
    figure_reference: str | None = Field(default=None, max_length=64)
    verification_status: str | None = Field(default=None, max_length=32)
    notes: str | None = None
    user_correction_json: str | None = None

    @field_validator("verification_status")
    @classmethod
    def _check_verification(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _validate_verification(value)


class EvidenceRecordRead(PersistenceSchema):
    """Payload returned when reading an evidence record."""

    id: int
    document_id: int
    extraction_run_id: int | None
    evidence_type: str
    field_key: str
    reported_value_json: str | None
    normalized_value_json: str | None
    units: str | None
    raw_source_text: str | None
    page_number: int | None
    section_title: str | None
    table_reference: str | None
    figure_reference: str | None
    extraction_method: str
    verification_status: str
    notes: str
    user_correction_json: str | None
    created_at: dt.datetime
    updated_at: dt.datetime
    version: int


class EvidenceExtractionRunCreate(PersistenceSchema):
    """Payload accepted when recording an extraction run."""

    document_id: int = Field(ge=1)
    status: str = Field(max_length=16)
    method: str = Field(max_length=16)
    pipeline_version: int = Field(default=1, ge=1)
    started_at: dt.datetime
    finished_at: dt.datetime | None = None
    duration_ms: int | None = Field(default=None, ge=0)
    ai_provider_snapshot: str | None = Field(default=None, max_length=64)
    ai_model_snapshot: str | None = Field(default=None, max_length=255)
    parameters_json: str | None = None
    error_message: str | None = None
    records_count: int = Field(default=0, ge=0)

    @field_validator("status")
    @classmethod
    def _check_status(cls, value: str) -> str:
        if value not in _VALID_RUN_STATUSES:
            raise ValueError(
                f"status must be one of {sorted(_VALID_RUN_STATUSES)}"
            )
        return value

    @field_validator("method")
    @classmethod
    def _check_method(cls, value: str) -> str:
        if value not in _VALID_RUN_METHODS:
            raise ValueError(
                f"method must be one of {sorted(_VALID_RUN_METHODS)}"
            )
        return value


class EvidenceExtractionRunRead(PersistenceSchema):
    """Payload returned when reading an extraction run."""

    id: int
    document_id: int
    status: str
    method: str
    pipeline_version: int
    started_at: dt.datetime
    finished_at: dt.datetime | None
    duration_ms: int | None
    ai_provider_snapshot: str | None
    ai_model_snapshot: str | None
    parameters_json: str | None
    error_message: str | None
    records_count: int
    created_at: dt.datetime
    updated_at: dt.datetime