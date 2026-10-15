"""Tests for ADR validation."""

from __future__ import annotations

from academic_platform.app.adr.model import ADR, ADRStatus
from academic_platform.app.adr.validator import validate_adr


def _valid_adr(**overrides) -> ADR:
    base = {
        "number": "0001",
        "title": "Test",
        "status": ADRStatus.ACCEPTED,
        "date": "2024-01-15",
        "context": "context",
        "decision": "decision",
        "consequences": "consequences",
    }
    base.update(overrides)
    return ADR(**base)


def test_valid_adr_has_no_issues() -> None:
    assert validate_adr(_valid_adr()) == []


def test_bad_date_format_is_reported() -> None:
    issues = validate_adr(_valid_adr(date="15-01-2024"))
    assert any(issue.field == "date" for issue in issues)


def test_invalid_calendar_date_is_reported() -> None:
    issues = validate_adr(_valid_adr(date="2024-13-45"))
    assert any(issue.field == "date" for issue in issues)


def test_empty_context_is_reported() -> None:
    issues = validate_adr(_valid_adr(context=""))
    assert any(issue.field == "context" for issue in issues)


def test_superseded_requires_superseded_by() -> None:
    issues = validate_adr(_valid_adr(status=ADRStatus.SUPERSEDED, superseded_by=None))
    assert any(issue.field == "superseded_by" for issue in issues)


def test_superseded_by_requires_superseded_status() -> None:
    issues = validate_adr(_valid_adr(status=ADRStatus.ACCEPTED, superseded_by="0002"))
    assert any(issue.field == "superseded_by" for issue in issues)


def test_invalid_number_is_reported() -> None:
    issues = validate_adr(_valid_adr(number="1"))
    assert any(issue.field == "number" for issue in issues)