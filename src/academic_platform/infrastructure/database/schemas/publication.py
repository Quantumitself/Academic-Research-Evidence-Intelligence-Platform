"""Pydantic schemas for the publication model."""

from __future__ import annotations

import datetime as dt

from pydantic import Field

from pydantic import field_validator

from academic_platform.infrastructure.database.schemas._base import PersistenceSchema


class PublicationCreate(PersistenceSchema):
    """Payload accepted when creating a publication."""

    key: str = Field(min_length=1, max_length=128)
    doi: str | None = Field(default=None, max_length=255)
    title: str = Field(default="", max_length=2048)
    authors_json: str | None = None
    year: int | None = Field(default=None, ge=0, le=3000)
    venue: str | None = Field(default=None, max_length=512)
    abstract: str | None = None
    language: str | None = Field(default=None, max_length=16)
    is_open_access: bool = False
    citation_count: int | None = Field(default=None, ge=0)
    source_providers_json: str = "[]"
    url: str | None = Field(default=None, max_length=2048)


class PublicationUpdate(PersistenceSchema):
    """Payload accepted when updating a publication."""

    title: str | None = Field(default=None, max_length=2048)
    authors_json: str | None = None
    year: int | None = Field(default=None, ge=0, le=3000)
    venue: str | None = Field(default=None, max_length=512)
    abstract: str | None = None
    language: str | None = Field(default=None, max_length=16)
    is_open_access: bool | None = None
    citation_count: int | None = Field(default=None, ge=0)
    source_providers_json: str | None = None
    url: str | None = Field(default=None, max_length=2048)


class PublicationRead(PersistenceSchema):
    """Payload returned when reading a publication."""

    id: int
    key: str
    doi: str | None
    title: str
    authors_json: str | None
    year: int | None
    venue: str | None
    abstract: str | None
    language: str | None
    is_open_access: bool
    citation_count: int | None
    source_providers_json: str
    url: str | None
    created_at: dt.datetime
    updated_at: dt.datetime
    version: int

    @field_validator("is_open_access", mode="before")
    @classmethod
    def _coerce_int_bool(cls, value: object) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, int):
            return value != 0
        return bool(value)