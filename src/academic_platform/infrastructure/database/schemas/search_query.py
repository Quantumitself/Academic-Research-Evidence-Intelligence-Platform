"""Pydantic schemas for the saved search query model."""

from __future__ import annotations

import datetime as dt

from pydantic import Field, field_validator

from academic_platform.infrastructure.database.schemas._base import PersistenceSchema

_VALID_SCOPES = {"all", "local", "remote"}


def _validate_scope(value: str) -> str:
    if value not in _VALID_SCOPES:
        raise ValueError(f"scope must be one of {sorted(_VALID_SCOPES)}")
    return value


class SavedSearchQueryCreate(PersistenceSchema):
    """Payload accepted when saving a search query."""

    key: str = Field(min_length=1, max_length=64)
    name: str = Field(default="", max_length=255)
    query_text: str = Field(default="", max_length=2048)
    scope: str = Field(default="all", max_length=16)
    filter_json: str | None = None
    source_ids_json: str = "[]"

    @field_validator("scope")
    @classmethod
    def _check_scope(cls, value: str) -> str:
        return _validate_scope(value)


class SavedSearchQueryUpdate(PersistenceSchema):
    """Payload accepted when updating a saved search query."""

    name: str | None = Field(default=None, max_length=255)
    query_text: str | None = Field(default=None, max_length=2048)
    scope: str | None = Field(default=None, max_length=16)
    filter_json: str | None = None
    source_ids_json: str | None = None
    last_executed_at: str | None = Field(default=None, max_length=64)

    @field_validator("scope")
    @classmethod
    def _check_scope(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _validate_scope(value)


class SavedSearchQueryRead(PersistenceSchema):
    """Payload returned when reading a saved search query."""

    id: int
    key: str
    name: str
    query_text: str
    scope: str
    filter_json: str | None
    source_ids_json: str
    last_executed_at: str | None
    created_at: dt.datetime
    updated_at: dt.datetime
    version: int