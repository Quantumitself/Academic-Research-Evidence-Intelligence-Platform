"""Tests for the ADR registry."""

from __future__ import annotations

from pathlib import Path

import pytest

from academic_platform.app.adr.model import ADR, ADRStatus, ADRValidationError
from academic_platform.app.adr.registry import ADRRegistry


def _adr(number: str, title: str, status: ADRStatus = ADRStatus.ACCEPTED, **overrides) -> ADR:
    base = {
        "number": number,
        "title": title,
        "status": status,
        "date": "2024-01-15",
        "context": "c",
        "decision": "d",
        "consequences": "k",
    }
    base.update(overrides)
    return ADR(**base)


def test_registry_rejects_duplicate_numbers() -> None:
    with pytest.raises(ADRValidationError):
        ADRRegistry([_adr("0001", "A"), _adr("0001", "B")])


def test_registry_orders_records_by_number() -> None:
    registry = ADRRegistry([_adr("0003", "C"), _adr("0001", "A"), _adr("0002", "B")])
    assert [record.number for record in registry.records] == ["0001", "0002", "0003"]


def test_registry_get_and_require() -> None:
    registry = ADRRegistry([_adr("0001", "A")])
    assert registry.get("0001") is not None
    assert registry.get("9999") is None
    assert registry.require("0001").title == "A"
    with pytest.raises(KeyError):
        registry.require("9999")


def test_registry_by_status() -> None:
    registry = ADRRegistry(
        [
            _adr("0001", "A", ADRStatus.ACCEPTED),
            _adr("0002", "B", ADRStatus.PROPOSED),
            _adr("0003", "C", ADRStatus.ACCEPTED),
        ]
    )
    assert {record.number for record in registry.by_status(ADRStatus.ACCEPTED)} == {"0001", "0003"}
    assert {record.number for record in registry.by_status(ADRStatus.PROPOSED)} == {"0002"}


def test_registry_search_matches_title_and_body() -> None:
    registry = ADRRegistry([_adr("0001", "Use SQLite")])
    assert registry.search("sqlite")[0].number == "0001"
    assert registry.search("nomatch") == ()


def test_registry_active_excludes_superseded() -> None:
    registry = ADRRegistry(
        [
            _adr("0001", "A", ADRStatus.ACCEPTED),
            _adr("0002", "B", ADRStatus.SUPERSEDED, superseded_by="0003"),
            _adr("0003", "C", ADRStatus.ACCEPTED),
        ]
    )
    assert {record.number for record in registry.active()} == {"0001", "0003"}


def test_registry_chain_resolution() -> None:
    registry = ADRRegistry(
        [
            _adr("0001", "A", ADRStatus.SUPERSEDED, superseded_by="0002"),
            _adr("0002", "B", ADRStatus.ACCEPTED, supersedes=("0001",)),
        ]
    )
    chain = registry.chain_for("0001")
    assert chain.origin.number == "0001"
    assert chain.superseded_by is not None
    assert chain.superseded_by.number == "0002"
    assert chain.supersedes == ()


def test_registry_from_directory(tmp_path: Path) -> None:
    (tmp_path / "0001-a.md").write_text(
        "# 0001. A\n\nStatus: accepted\nDate: 2024-01-15\n\n"
        "## Context\n\nc\n\n## Decision\n\nd\n\n## Consequences\n\nk\n",
        encoding="utf-8",
    )
    registry = ADRRegistry.from_directory(tmp_path)
    assert len(registry.records) == 1
    assert registry.errors == ()