"""Tests for the evidence Pydantic schemas."""

from __future__ import annotations

import datetime as dt

import pytest
from pydantic import ValidationError

from academic_platform.infrastructure.database.schemas import (
    EvidenceExtractionRunCreate,
    EvidenceRecordCreate,
    EvidenceRecordUpdate,
)


def test_create_defaults() -> None:
    payload = EvidenceRecordCreate(document_id=1, evidence_type="sample_size")
    assert payload.extraction_method == "rule_based"
    assert payload.verification_status == "ai_proposed"


def test_create_rejects_bad_type() -> None:
    with pytest.raises(ValidationError):
        EvidenceRecordCreate(document_id=1, evidence_type="bogus")


def test_create_rejects_bad_verification() -> None:
    with pytest.raises(ValidationError):
        EvidenceRecordCreate(
            document_id=1,
            evidence_type="sample_size",
            verification_status="bogus",
        )


def test_update_all_optional() -> None:
    payload = EvidenceRecordUpdate()
    assert payload.verification_status is None


def test_update_rejects_bad_verification() -> None:
    with pytest.raises(ValidationError):
        EvidenceRecordUpdate(verification_status="bogus")


def test_run_create_rejects_bad_status() -> None:
    with pytest.raises(ValidationError):
        EvidenceExtractionRunCreate(
            document_id=1,
            status="bogus",
            method="rule_based",
            started_at=dt.datetime(2024, 1, 1),
        )


def test_run_create_rejects_bad_method() -> None:
    with pytest.raises(ValidationError):
        EvidenceExtractionRunCreate(
            document_id=1,
            status="running",
            method="bogus",
            started_at=dt.datetime(2024, 1, 1),
        )