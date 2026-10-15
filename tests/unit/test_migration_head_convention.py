"""Tests that the migration-head convention is honored across the test suite.

This module asserts that no test file hard-codes the current head revision
as a string literal. The rule is documented in ``docs/code_style.md`` and
``docs/testing.md``: tests import ``EXPECTED_HEAD`` from
``tests.unit._migration_head``; specific revisions may appear only as
literal downgrade targets.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from academic_platform.infrastructure.database.migrations import (
    declared_head_revision,
)

_HEAD_PATTERN = re.compile(r'"([0-9]{4}_[a-z0-9_]+)"')


def _test_files() -> list[Path]:
    repo_root = Path(__file__).resolve().parents[2]
    tests_root = repo_root / "tests"
    return sorted(tests_root.rglob("*.py"))


def test_no_test_hard_codes_current_head_as_literal() -> None:
    head = declared_head_revision()
    offending: list[str] = []
    for path in _test_files():
        if path.name == "_migration_head.py":
            continue
        text = path.read_text(encoding="utf-8")
        for match in _HEAD_PATTERN.finditer(text):
            if match.group(1) == head:
                offending.append(f"{path.name}:{match.start()}")
    assert not offending, offending


def test_expected_head_is_a_string() -> None:
    head = declared_head_revision()
    assert isinstance(head, str)
    assert head


def test_migration_head_helper_available_in_production() -> None:
    from academic_platform.infrastructure.database import declared_head_revision as fn

    assert callable(fn)
    assert fn() == declared_head_revision()