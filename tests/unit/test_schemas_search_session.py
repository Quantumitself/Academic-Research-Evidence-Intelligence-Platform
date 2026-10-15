"""Tests for the search session Pydantic schemas."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from academic_platform.infrastructure.database.schemas import (
    SearchResultCreate,
    SearchSessionCreate,
)


def test_session_create_defaults() -> None:
    payload = SearchSessionCreate()
    assert payload.scope == "all"
    assert payload.partial is False
    assert payload.result_count == 0


def test_session_create_rejects_invalid_scope() -> None:
    with pytest.raises(ValidationError):
        SearchSessionCreate(scope="bogus")


def test_result_create_defaults() -> None:
    payload = SearchResultCreate(
        session_id=1,
        publication_id=1,
        provider_key="crossref",
    )
    assert payload.rank == 0
    assert payload.score is None


def test_result_create_requires_positive_ids() -> None:
    with pytest.raises(ValidationError):
        SearchResultCreate(session_id=0, publication_id=1, provider_key="x")