"""Tests for the duplicate detection policy."""

from __future__ import annotations

import pytest

from academic_platform.application.deduplication.policy import (
    DuplicatePolicy,
)


def test_defaults() -> None:
    policy = DuplicatePolicy()
    assert policy.use_checksum is True
    assert policy.use_doi is True
    assert policy.use_metadata is True
    assert policy.require_author_match is True
    assert policy.allow_year_difference is True
    assert policy.metadata_candidate_limit == 500


def test_rejects_zero_candidate_limit() -> None:
    with pytest.raises(ValueError):
        DuplicatePolicy(metadata_candidate_limit=0)


def test_rejects_no_signals_enabled() -> None:
    with pytest.raises(ValueError):
        DuplicatePolicy(
            use_checksum=False,
            use_doi=False,
            use_metadata=False,
        )