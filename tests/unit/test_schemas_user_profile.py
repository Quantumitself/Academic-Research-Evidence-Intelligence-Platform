"""Tests for the UserProfile Pydantic schemas."""

from __future__ import annotations

import datetime as dt

import pytest
from pydantic import ValidationError

from academic_platform.infrastructure.database.schemas import (
    UserProfileCreate,
    UserProfileRead,
    UserProfileUpdate,
)


def test_create_accepts_valid_key() -> None:
    payload = UserProfileCreate(key="alice")
    assert payload.key == "alice"


@pytest.mark.parametrize(
    "bad_key",
    ["", "Alice", "al ice", "-alice", "alice!"],
)
def test_create_rejects_invalid_key(bad_key: str) -> None:
    with pytest.raises(ValidationError):
        UserProfileCreate(key=bad_key)


def test_create_rejects_unknown_field() -> None:
    with pytest.raises(ValidationError):
        UserProfileCreate(key="alice", unknown="x")  # type: ignore[call-arg]


def test_update_all_fields_optional() -> None:
    payload = UserProfileUpdate()
    assert payload.display_name is None


def test_read_from_attributes() -> None:
    class _Row:
        id = 1
        key = "alice"
        display_name = "Alice"
        preferred_language = None
        institution = None
        notes = None
        created_at = dt.datetime(2024, 1, 1)
        updated_at = dt.datetime(2024, 1, 1)
        version = 1

    payload = UserProfileRead.model_validate(_Row())
    assert payload.key == "alice"