"""Pydantic schemas for the search session and search result models."""

from __future__ import annotations

import datetime as dt

from pydantic import Field, field_validator

from academic_platform.infrastructure.database.schemas._base import PersistenceSchema

_VALID_SCOPES = {"all", "local", "remote"}


def _validate_scope(value: str) -> str:
    if value not in _VALID_SCOPES:
        raise ValueError(f"scope must be one of {sorted(_VALID_SCOPES)}")
    return value


class SearchSessionCreate(PersistenceSchema):
    """Payload accepted when recording a search session."""

    query_id: int | None = Field(default=None, ge=1)
    query_text: str = Field(default="", max_length=2048)
    scope: str = Field(default="all", max_length=16)
    executed_at: dt.datetime | None = None
    source_reports_json: str = "[]"
    partial: bool = False
    result_count: int = Field(default=0, ge=0)
    message: str = ""

    @field_validator("scope")
    @classmethod
    def _check_scope(cls, value: str) -> str:
        return _validate_scope(value)


class SearchSessionRead(PersistenceSchema):
    """Payload returned when reading a search session."""

    id: int
    query_id: int | None
    query_text: str
    scope: str
    executed_at: dt.datetime
    source_reports_json: str
    partial: bool
    result_count: int
    message: str
    created_at: dt.datetime
    updated_at: dt.datetime

    @field_validator("partial", mode="before")
    @classmethod
    def _coerce_int_bool(cls, value: object) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, int):
            return value != 0
        return bool(value)


class SearchResultCreate(PersistenceSchema):
    """Payload accepted when recording a search result."""

    session_id: int = Field(ge=1)
    publication_id: int = Field(ge=1)
    provider_key: str = Field(min_length=1, max_length=64)
    rank: int = Field(default=0, ge=0)
    score: float | None = None
    source_url: str | None = Field(default=None, max_length=2048)


class SearchResultRead(PersistenceSchema):
    """Payload returned when reading a search result."""

    id: int
    session_id: int
    publication_id: int
    provider_key: str
    rank: int
    score: float | None
    source_url: str | None
    created_at: dt.datetime
    updated_at: dt.datetime