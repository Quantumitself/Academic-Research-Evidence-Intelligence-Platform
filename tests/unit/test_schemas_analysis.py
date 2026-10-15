"""Tests for the analysis Pydantic schemas."""

from __future__ import annotations

import datetime as dt

import pytest
from pydantic import ValidationError

from academic_platform.infrastructure.database.schemas import (
    AnalysisInputCreate,
    AnalysisRunCreate,
    SynthesisReportCreate,
)


def test_run_create_defaults() -> None:
    payload = AnalysisRunCreate(
        analysis_type="descriptive",
        status="running",
        started_at=dt.datetime(2024, 1, 1),
    )
    assert payload.engine_version == 1
    assert payload.inputs_count == 0


def test_run_create_rejects_bad_type() -> None:
    with pytest.raises(ValidationError):
        AnalysisRunCreate(
            analysis_type="bogus",
            status="running",
            started_at=dt.datetime(2024, 1, 1),
        )


def test_run_create_rejects_bad_status() -> None:
    with pytest.raises(ValidationError):
        AnalysisRunCreate(
            analysis_type="descriptive",
            status="bogus",
            started_at=dt.datetime(2024, 1, 1),
        )


def test_input_create_rejects_bad_value_kind() -> None:
    with pytest.raises(ValidationError):
        AnalysisInputCreate(
            analysis_run_id=1,
            input_key="k",
            value_kind="bogus",
        )


def test_synthesis_create_defaults() -> None:
    payload = SynthesisReportCreate(report_kind="narrative")
    assert payload.contributing_run_ids_json == "[]"
    assert payload.included_evidence_ids_json == "[]"


def test_synthesis_create_rejects_bad_kind() -> None:
    with pytest.raises(ValidationError):
        SynthesisReportCreate(report_kind="bogus")