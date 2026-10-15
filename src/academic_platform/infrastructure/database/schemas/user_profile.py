"""Pydantic schemas for the user profile model."""

from __future__ import annotations

import datetime as dt
import re

from pydantic import Field, field_validator

from academic_platform.infrastructure.database.schemas._base import PersistenceSchema

_KEY_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")


class UserProfileCreate(PersistenceSchema):
    """Payload accepted when creating a user profile."""

    key: str = Field(min_length=1, max_length=64)
    display_name: str = Field(default="", max_length=255)
    preferred_language: str | None = Field(default=None, max_length=16)
    institution: str | None = Field(default=None, max_length=255)
    notes: str | None = Field(default=None, max_length=4096)

    @field_validator("key")
    @classmethod
    def _validate_key(cls, value: str) -> str:
        if not _KEY_PATTERN.match(value):
            raise ValueError(
                "key must match ^[a-z0-9][a-z0-9_-]{0,63}$"
            )
        return value


class UserProfileUpdate(PersistenceSchema):
    """Payload accepted when updating a user profile.

    Every field is optional. Absent fields are left unchanged.
    """

    display_name: str | None = Field(default=None, max_length=255)
    preferred_language: str | None = Field(default=None, max_length=16)
    institution: str | None = Field(default=None, max_length=255)
    notes: str | None = Field(default=None, max_length=4096)


class UserProfileRead(PersistenceSchema):
    """Payload returned when reading a user profile."""

    id: int
    key: str
    display_name: str
    preferred_language: str | None
    institution: str | None
    notes: str | None
    created_at: dt.datetime
    updated_at: dt.datetime
    version: int