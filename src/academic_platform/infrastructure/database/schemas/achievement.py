"""Pydantic schemas for the achievement, unlock, and user activity models."""

from __future__ import annotations

import datetime as dt

from pydantic import Field, field_validator

from academic_platform.infrastructure.database.schemas._base import PersistenceSchema

_VALID_ACTIVITY_KINDS = {
    "app_started",
    "project_created",
    "project_updated",
    "document_imported",
    "search_executed",
    "collection_created",
    "evidence_extracted",
    "evidence_verified",
    "analysis_run",
    "guide_generated",
    "achievement_unlocked",
    "settings_changed",
}


def _validate_activity_kind(value: str) -> str:
    if value not in _VALID_ACTIVITY_KINDS:
        raise ValueError(
            f"activity_kind must be one of {sorted(_VALID_ACTIVITY_KINDS)}"
        )
    return value


class AchievementCreate(PersistenceSchema):
    """Payload accepted when defining an achievement."""

    key: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=255)
    description: str = ""
    category: str = Field(default="general", max_length=32)
    points: int = Field(default=0, ge=0)
    active: bool = True


class AchievementRead(PersistenceSchema):
    """Payload returned when reading an achievement."""

    id: int
    key: str
    title: str
    description: str
    category: str
    points: int
    active: bool
    created_at: dt.datetime
    updated_at: dt.datetime
    version: int

    @field_validator("active", mode="before")
    @classmethod
    def _coerce_int_bool(cls, value: object) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, int):
            return value != 0
        return bool(value)


class AchievementUnlockCreate(PersistenceSchema):
    """Payload accepted when recording an unlock."""

    achievement_id: int = Field(ge=1)
    user_key: str = Field(min_length=1, max_length=64)
    unlocked_at: dt.datetime | None = None
    trigger_event: str | None = Field(default=None, max_length=64)


class AchievementUnlockRead(PersistenceSchema):
    """Payload returned when reading an unlock."""

    id: int
    achievement_id: int
    user_key: str
    unlocked_at: dt.datetime
    trigger_event: str | None
    created_at: dt.datetime
    updated_at: dt.datetime


class UserActivityCreate(PersistenceSchema):
    """Payload accepted when appending an activity record."""

    user_key: str = Field(default="system", max_length=64)
    activity_kind: str = Field(max_length=32)
    summary: str = Field(default="", max_length=512)
    target_type: str | None = Field(default=None, max_length=64)
    target_identifier: str | None = Field(default=None, max_length=128)
    payload_json: str | None = None
    occurred_at: dt.datetime | None = None

    @field_validator("activity_kind")
    @classmethod
    def _check_kind(cls, value: str) -> str:
        return _validate_activity_kind(value)


class UserActivityRead(PersistenceSchema):
    """Payload returned when reading an activity record."""

    id: int
    user_key: str
    activity_kind: str
    summary: str
    target_type: str | None
    target_identifier: str | None
    payload_json: str | None
    occurred_at: dt.datetime
    created_at: dt.datetime
    updated_at: dt.datetime