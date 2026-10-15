"""Pydantic schemas for the research question model."""

from __future__ import annotations

import datetime as dt

from pydantic import Field, field_validator

from academic_platform.infrastructure.database.schemas._base import PersistenceSchema

_VALID_KINDS = {"main", "sub", "exploratory", "hypothesis"}


def _validate_kind(value: str) -> str:
    if value not in _VALID_KINDS:
        raise ValueError(f"kind must be one of {sorted(_VALID_KINDS)}")
    return value


class ResearchQuestionCreate(PersistenceSchema):
    """Payload accepted when creating a research question."""

    project_id: int = Field(ge=1)
    text: str = Field(min_length=1, max_length=2048)
    kind: str = Field(default="main", max_length=32)
    is_primary: bool = False
    position: int = Field(default=0, ge=0)

    @field_validator("kind")
    @classmethod
    def _check_kind(cls, value: str) -> str:
        return _validate_kind(value)


class ResearchQuestionUpdate(PersistenceSchema):
    """Payload accepted when updating a research question."""

    text: str | None = Field(default=None, max_length=2048)
    kind: str | None = Field(default=None, max_length=32)
    is_primary: bool | None = None
    position: int | None = Field(default=None, ge=0)

    @field_validator("kind")
    @classmethod
    def _check_kind(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _validate_kind(value)


class ResearchQuestionRead(PersistenceSchema):
    """Payload returned when reading a research question."""

    id: int
    project_id: int
    text: str
    kind: str
    is_primary: bool
    position: int
    created_at: dt.datetime
    updated_at: dt.datetime
    version: int

    @field_validator("is_primary", mode="before")
    @classmethod
    def _coerce_int_bool(cls, value: object) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, int):
            return value != 0
        return bool(value)