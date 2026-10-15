"""Integration test: the repository's own ADR set parses cleanly."""

from __future__ import annotations

from pathlib import Path

from academic_platform.app.adr.registry import ADRRegistry


def test_repository_adrs_are_valid() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    adr_dir = repo_root / "docs" / "adr"
    registry = ADRRegistry.from_directory(adr_dir)
    assert not registry.errors, [msg for _, msg in registry.errors]
    assert len(registry.records) >= 6


def test_repository_adrs_are_unique_and_ordered() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    adr_dir = repo_root / "docs" / "adr"
    registry = ADRRegistry.from_directory(adr_dir)
    numbers = [record.number for record in registry.records]
    assert numbers == sorted(numbers)
    assert len(numbers) == len(set(numbers))