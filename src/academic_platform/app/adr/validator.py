"""Validation for parsed ADR content.

The validator checks both structural conformance (required sections present)
and semantic sanity (status string recognized, date format valid, cross
references well-formed). Validation issues are returned as a list so that
callers can decide whether to raise or to report.
"""

from __future__ import annotations

import re
from datetime import date

from academic_platform.app.adr.model import ADR, ADRStatus, ADRValidationIssue

_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_NUMBER_PATTERN = re.compile(r"^\d{4}$")
_REFERENCE_PATTERN = re.compile(r"^\d{4}$")

_REQUIRED_SECTIONS = ("context", "decision", "consequences")


def _check_date(value: str) -> ADRValidationIssue | None:
    if not _DATE_PATTERN.match(value):
        return ADRValidationIssue(
            field="date",
            message="must be in ISO-8601 format (YYYY-MM-DD)",
        )
    try:
        date.fromisoformat(value)
    except ValueError:
        return ADRValidationIssue(
            field="date",
            message=f"{value!r} is not a valid calendar date",
        )
    return None


def _check_number(value: str, field_name: str) -> ADRValidationIssue | None:
    if not _NUMBER_PATTERN.match(value):
        return ADRValidationIssue(
            field=field_name,
            message="must be a zero-padded four-digit number",
        )
    return None


def validate_adr(adr: ADR) -> list[ADRValidationIssue]:
    """Return the list of validation issues for the given ADR.

    An empty list indicates that the record is fully valid.
    """
    issues: list[ADRValidationIssue] = []

    number_issue = _check_number(adr.number, "number")
    if number_issue is not None:
        issues.append(number_issue)

    if not adr.title.strip():
        issues.append(ADRValidationIssue(field="title", message="must not be empty"))

    if not isinstance(adr.status, ADRStatus):
        issues.append(
            ADRValidationIssue(
                field="status",
                message=f"unrecognized status {adr.status!r}",
            )
        )

    date_issue = _check_date(adr.date)
    if date_issue is not None:
        issues.append(date_issue)

    for section_name in _REQUIRED_SECTIONS:
        content = getattr(adr, section_name)
        if not content or not content.strip():
            issues.append(
                ADRValidationIssue(
                    field=section_name,
                    message="required section is empty",
                )
            )

    for reference in adr.supersedes:
        ref_issue = _check_number(reference, "supersedes")
        if ref_issue is not None:
            issues.append(ref_issue)

    if adr.superseded_by is not None:
        ref_issue = _check_number(adr.superseded_by, "superseded_by")
        if ref_issue is not None:
            issues.append(ref_issue)

    if adr.status is ADRStatus.SUPERSEDED and adr.superseded_by is None:
        issues.append(
            ADRValidationIssue(
                field="superseded_by",
                message="required when status is 'superseded'",
            )
        )

    if adr.status is not ADRStatus.SUPERSEDED and adr.superseded_by is not None:
        issues.append(
            ADRValidationIssue(
                field="superseded_by",
                message="only meaningful when status is 'superseded'",
            )
        )

    return issues