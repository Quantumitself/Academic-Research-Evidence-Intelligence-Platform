"""Pydantic schemas for the research guide, section, and citation models."""

from __future__ import annotations

import datetime as dt

from pydantic import Field, field_validator

from academic_platform.infrastructure.database.schemas._base import PersistenceSchema

_VALID_GUIDE_KINDS = {"topic", "project", "collection", "papers"}
_VALID_SOURCE_TYPES = {"publication", "document", "evidence", "external"}


def _validate_guide_kind(value: str) -> str:
    if value not in _VALID_GUIDE_KINDS:
        raise ValueError(f"guide_kind must be one of {sorted(_VALID_GUIDE_KINDS)}")
    return value


def _validate_source_type(value: str) -> str:
    if value not in _VALID_SOURCE_TYPES:
        raise ValueError(
            f"source_type must be one of {sorted(_VALID_SOURCE_TYPES)}"
        )
    return value


class ResearchGuideCreate(PersistenceSchema):
    """Payload accepted when creating a research guide."""

    key: str = Field(min_length=1, max_length=64)
    title: str = Field(default="", max_length=512)
    guide_kind: str = Field(max_length=32)
    topic: str = Field(default="", max_length=1024)
    project_id: int | None = Field(default=None, ge=1)
    collection_id: int | None = Field(default=None, ge=1)
    overview: str = ""
    generated_by: str = Field(default="user", max_length=32)

    @field_validator("guide_kind")
    @classmethod
    def _check_kind(cls, value: str) -> str:
        return _validate_guide_kind(value)


class ResearchGuideUpdate(PersistenceSchema):
    """Payload accepted when updating a research guide."""

    title: str | None = Field(default=None, max_length=512)
    topic: str | None = Field(default=None, max_length=1024)
    overview: str | None = None


class ResearchGuideRead(PersistenceSchema):
    """Payload returned when reading a research guide."""

    id: int
    key: str
    title: str
    guide_kind: str
    topic: str
    project_id: int | None
    collection_id: int | None
    overview: str
    generated_by: str
    created_at: dt.datetime
    updated_at: dt.datetime
    version: int


class ResearchGuideSectionCreate(PersistenceSchema):
    """Payload accepted when creating a guide section."""

    guide_id: int = Field(ge=1)
    heading: str = Field(default="", max_length=512)
    body: str = ""
    position: int = Field(default=0, ge=0)
    is_source_derived: bool = False


class ResearchGuideSectionUpdate(PersistenceSchema):
    """Payload accepted when updating a guide section."""

    heading: str | None = Field(default=None, max_length=512)
    body: str | None = None
    position: int | None = Field(default=None, ge=0)
    is_source_derived: bool | None = None


class ResearchGuideSectionRead(PersistenceSchema):
    """Payload returned when reading a guide section."""

    id: int
    guide_id: int
    heading: str
    body: str
    position: int
    is_source_derived: bool
    created_at: dt.datetime
    updated_at: dt.datetime

    @field_validator("is_source_derived", mode="before")
    @classmethod
    def _coerce_int_bool(cls, value: object) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, int):
            return value != 0
        return bool(value)


class CitationRecordCreate(PersistenceSchema):
    """Payload accepted when creating a citation record."""

    section_id: int = Field(ge=1)
    source_type: str = Field(max_length=16)
    source_identifier: str = Field(min_length=1, max_length=255)
    quoted_text: str | None = None
    page_number: int | None = Field(default=None, ge=1)
    note: str = ""

    @field_validator("source_type")
    @classmethod
    def _check_source_type(cls, value: str) -> str:
        return _validate_source_type(value)


class CitationRecordRead(PersistenceSchema):
    """Payload returned when reading a citation record."""

    id: int
    section_id: int
    source_type: str
    source_identifier: str
    quoted_text: str | None
    page_number: int | None
    note: str
    created_at: dt.datetime
    updated_at: dt.datetime