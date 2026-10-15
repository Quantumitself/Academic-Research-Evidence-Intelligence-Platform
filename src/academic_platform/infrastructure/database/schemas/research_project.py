"""Pydantic schemas for the research project model."""

from __future__ import annotations

import datetime as dt
import re

from pydantic import Field, field_validator

from academic_platform.infrastructure.database.schemas._base import PersistenceSchema

_KEY_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
_VALID_STAGES = {
    "idea",
    "design",
    "collection",
    "analysis",
    "writing",
    "complete",
    "archived",
}


def _validate_key(value: str) -> str:
    if not _KEY_PATTERN.match(value):
        raise ValueError("key must match ^[a-z0-9][a-z0-9_-]{0,63}$")
    return value


def _validate_stage(value: str) -> str:
    if value not in _VALID_STAGES:
        raise ValueError(f"stage must be one of {sorted(_VALID_STAGES)}")
    return value


class ResearchProjectCreate(PersistenceSchema):
    """Payload accepted when creating a research project."""

    key: str = Field(min_length=1, max_length=64)
    title: str = Field(default="", max_length=512)
    topic: str = Field(default="", max_length=1024)
    stage: str = Field(default="idea", max_length=32)
    project_metadata: str | None = None

    @field_validator("key")
    @classmethod
    def _check_key(cls, value: str) -> str:
        return _validate_key(value)

    @field_validator("stage")
    @classmethod
    def _check_stage(cls, value: str) -> str:
        return _validate_stage(value)


class ResearchProjectUpdate(PersistenceSchema):
    """Payload accepted when updating a research project."""

    title: str | None = Field(default=None, max_length=512)
    topic: str | None = Field(default=None, max_length=1024)
    stage: str | None = Field(default=None, max_length=32)
    project_metadata: str | None = None

    @field_validator("stage")
    @classmethod
    def _check_stage(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _validate_stage(value)


class ResearchProjectRead(PersistenceSchema):
    """Payload returned when reading a research project."""

    id: int
    key: str
    title: str
    topic: str
    stage: str
    project_metadata: str | None
    created_at: dt.datetime
    updated_at: dt.datetime
    version: int