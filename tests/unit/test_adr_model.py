"""Tests for the ADR data model."""

from __future__ import annotations

from academic_platform.app.adr.model import ADR, ADRStatus


def test_slug_is_filesystem_safe() -> None:
    adr = ADR(
        number="0001",
        title="Use a modular monolith architecture",
        status=ADRStatus.ACCEPTED,
        date="2024-01-15",
    )
    assert adr.slug == "0001-use-a-modular-monolith-architecture"


def test_slug_collapses_repeated_separators() -> None:
    adr = ADR(
        number="0002",
        title="Use  PySide6 -- Qt for  Python",
        status=ADRStatus.ACCEPTED,
        date="2024-01-15",
    )
    slug = adr.slug
    assert "--" not in slug
    assert slug.startswith("0002-")


def test_is_active_for_accepted_and_proposed() -> None:
    accepted = ADR("0001", "T", ADRStatus.ACCEPTED, "2024-01-15")
    proposed = ADR("0002", "T", ADRStatus.PROPOSED, "2024-01-15")
    rejected = ADR("0003", "T", ADRStatus.REJECTED, "2024-01-15")
    deprecated = ADR("0004", "T", ADRStatus.DEPRECATED, "2024-01-15")
    superseded = ADR("0005", "T", ADRStatus.SUPERSEDED, "2024-01-15", superseded_by="0006")

    assert accepted.is_active
    assert proposed.is_active
    assert not rejected.is_active
    assert not deprecated.is_active
    assert not superseded.is_active