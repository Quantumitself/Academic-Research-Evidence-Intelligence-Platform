"""Tests for the saved search query Pydantic schemas."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from academic_platform.infrastructure.database.schemas import (
    SavedSearchQueryCreate,
    SavedSearchQueryUpdate,
)


def test_create_defaults() -> None:
    payload = SavedSearchQueryCreate(key="q1")
    assert payload.scope == "all"
    assert payload.source_ids_json == "[]"


def test_create_rejects_invalid_scope() -> None:
    with pytest.raises(ValidationError):
        SavedSearchQueryCreate(key="q1", scope="bogus")


def test_update_all_optional() -> None:
    payload = SavedSearchQueryUpdate()
    assert payload.scope is None


def test_update_rejects_invalid_scope() -> None:
    with pytest.raises(ValidationError):
        SavedSearchQueryUpdate(scope="bogus")