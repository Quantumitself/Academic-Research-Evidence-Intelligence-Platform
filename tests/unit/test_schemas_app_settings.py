"""Tests for the AppSettings Pydantic schemas."""

from __future__ import annotations

import datetime as dt

import pytest
from pydantic import ValidationError

from academic_platform.infrastructure.database.schemas import (
    AppSettingsRead,
    AppSettingsUpsert,
)


def test_upsert_defaults() -> None:
    payload = AppSettingsUpsert()
    assert payload.active_user_key is None
    assert payload.settings_schema_version == 1


def test_upsert_rejects_nonpositive_schema_version() -> None:
    with pytest.raises(ValidationError):
        AppSettingsUpsert(settings_schema_version=0)


def test_read_from_attributes() -> None:
    class _Row:
        id = 1
        active_user_key = "alice"
        settings_schema_version = 1
        created_at = dt.datetime(2024, 1, 1)
        updated_at = dt.datetime(2024, 1, 1)

    payload = AppSettingsRead.model_validate(_Row())
    assert payload.active_user_key == "alice"