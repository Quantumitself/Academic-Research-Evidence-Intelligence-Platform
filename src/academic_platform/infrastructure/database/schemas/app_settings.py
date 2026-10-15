"""Pydantic schemas for the app settings model."""

from __future__ import annotations

import datetime as dt

from pydantic import Field

from academic_platform.infrastructure.database.schemas._base import PersistenceSchema


class AppSettingsUpsert(PersistenceSchema):
    """Payload accepted when writing the singleton settings row."""

    active_user_key: str | None = Field(default=None, max_length=64)
    settings_schema_version: int = Field(default=1, ge=1)


class AppSettingsRead(PersistenceSchema):
    """Payload returned when reading the singleton settings row."""

    id: int
    active_user_key: str | None
    settings_schema_version: int
    created_at: dt.datetime
    updated_at: dt.datetime