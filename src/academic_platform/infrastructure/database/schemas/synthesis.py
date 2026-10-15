"""Pydantic schemas for the synthesis report model."""

from __future__ import annotations

import datetime as dt

from pydantic import Field, field_validator

from academic_platform.infrastructure.database.schemas._base import PersistenceSchema

_VALID_REPORT_KINDS = {"narrative", "meta_analysis", "mixed"}


def _validate_report_kind(value: str) -> str:
    if value not in _VALID_REPORT_KINDS:
        raise ValueError(
            f"report_kind must be one of {sorted(_VALID_REPORT_KINDS)}"
        )
    return value


class SynthesisReportCreate(PersistenceSchema):
    """Payload accepted when creating a synthesis report."""

    collection_id: int | None = Field(default=None, ge=1)
    report_kind: str = Field(max_length=32)
    title: str = Field(default="", max_length=512)
    narrative: str = ""
    contributing_run_ids_json: str = "[]"
    included_evidence_ids_json: str = "[]"
    excluded_evidence_ids_json: str = "[]"
    exclusion_reasons_json: str | None = None
    limitations_json: str | None = None
    reproducibility_json: str | None = None

    @field_validator("report_kind")
    @classmethod
    def _check_kind(cls, value: str) -> str:
        return _validate_report_kind(value)


class SynthesisReportUpdate(PersistenceSchema):
    """Payload accepted when updating a synthesis report."""

    title: str | None = Field(default=None, max_length=512)
    narrative: str | None = None
    contributing_run_ids_json: str | None = None
    included_evidence_ids_json: str | None = None
    excluded_evidence_ids_json: str | None = None
    exclusion_reasons_json: str | None = None
    limitations_json: str | None = None
    reproducibility_json: str | None = None


class SynthesisReportRead(PersistenceSchema):
    """Payload returned when reading a synthesis report."""

    id: int
    collection_id: int | None
    report_kind: str
    title: str
    narrative: str
    contributing_run_ids_json: str
    included_evidence_ids_json: str
    excluded_evidence_ids_json: str
    exclusion_reasons_json: str | None
    limitations_json: str | None
    reproducibility_json: str | None
    created_at: dt.datetime
    updated_at: dt.datetime
    version: int