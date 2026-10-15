"""Tests for the ADR parser."""

from __future__ import annotations

from pathlib import Path

import pytest

from academic_platform.app.adr.model import ADRStatus, ADRValidationError
from academic_platform.app.adr.parser import parse_adr_directory, parse_adr_file

VALID_ADR = """# 0001. Use a modular monolith architecture

Status: accepted
Date: 2024-01-15
Deciders: Architecture Team

## Context

Context text.

## Decision

Decision text.

## Consequences

Consequence text.

## Alternatives

Alternatives text.

## References

- Product specification.
"""


def _write(path: Path, content: str) -> Path:
    path.write_text(content, encoding="utf-8")
    return path


def test_parse_valid_adr(tmp_path: Path) -> None:
    path = _write(tmp_path / "0001-test.md", VALID_ADR)
    record = parse_adr_file(path)
    assert record.number == "0001"
    assert record.title == "Use a modular monolith architecture"
    assert record.status is ADRStatus.ACCEPTED
    assert record.date == "2024-01-15"
    assert "Context text." in record.context
    assert "Decision text." in record.decision
    assert "Consequence text." in record.consequences
    assert record.source_path == path


def test_parse_missing_title_raises(tmp_path: Path) -> None:
    path = _write(tmp_path / "bad.md", "Not a title\nStatus: accepted\n")
    with pytest.raises(ADRValidationError):
        parse_adr_file(path)


def test_parse_unknown_status_raises(tmp_path: Path) -> None:
    content = VALID_ADR.replace("Status: accepted", "Status: unknown")
    path = _write(tmp_path / "0001-test.md", content)
    with pytest.raises(ADRValidationError):
        parse_adr_file(path)


def test_parse_missing_required_section_raises(tmp_path: Path) -> None:
    content = VALID_ADR.replace("## Context\n\nContext text.\n\n", "")
    path = _write(tmp_path / "0001-test.md", content)
    with pytest.raises(ADRValidationError):
        parse_adr_file(path)


def test_parse_directory_skips_readme_and_template(tmp_path: Path) -> None:
    _write(tmp_path / "0001-test.md", VALID_ADR)
    _write(tmp_path / "README.md", "# Index\n")
    _write(tmp_path / "TEMPLATE.md", "# Template\n")
    records, errors = parse_adr_directory(tmp_path)
    assert not errors
    assert len(records) == 1


def test_parse_directory_reports_errors(tmp_path: Path) -> None:
    _write(tmp_path / "0001-good.md", VALID_ADR)
    _write(tmp_path / "0002-bad.md", "# not a number\n")
    records, errors = parse_adr_directory(tmp_path)
    assert len(records) == 1
    assert len(errors) == 1