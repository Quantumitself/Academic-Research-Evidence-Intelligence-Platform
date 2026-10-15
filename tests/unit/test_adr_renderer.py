"""Tests for the ADR renderer."""

from __future__ import annotations

from academic_platform.app.adr.model import ADR, ADRStatus
from academic_platform.app.adr.registry import ADRRegistry
from academic_platform.app.adr.renderer import render_detail, render_index


def _adr(number: str, title: str, status: ADRStatus = ADRStatus.ACCEPTED) -> ADR:
    return ADR(
        number=number,
        title=title,
        status=status,
        date="2024-01-15",
        context="Context body.",
        decision="Decision body.",
        consequences="Consequence body.",
    )


def test_render_index_lists_all_records() -> None:
    registry = ADRRegistry([_adr("0001", "A"), _adr("0002", "B")])
    rendered = render_index(registry)
    assert "# Architecture Decision Records" in rendered
    assert "0001" in rendered
    assert "0002" in rendered


def test_render_index_reports_unparseable_files() -> None:
    registry = ADRRegistry([], errors=[(__import__("pathlib").Path("bad.md"), "invalid")])
    rendered = render_index(registry)
    assert "Unparseable files" in rendered or "Files requiring attention" in rendered
    assert "bad.md" in rendered


def test_render_detail_contains_sections() -> None:
    rendered = render_detail(_adr("0001", "A"))
    assert "# ADR 0001" in rendered
    assert "## Context" in rendered
    assert "## Decision" in rendered
    assert "## Consequences" in rendered