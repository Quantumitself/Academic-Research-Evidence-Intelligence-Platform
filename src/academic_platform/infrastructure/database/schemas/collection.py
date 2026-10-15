"""Pydantic schemas for the collection and collection item models."""

from __future__ import annotations

import datetime as dt
import re

from pydantic import Field, field_validator

from academic_platform.infrastructure.database.schemas._base import PersistenceSchema

_KEY_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
_VALID_COLLECTION_KINDS = {"manual", "topic", "project", "saved_search", "smart"}
_VALID_ITEM_TYPES = {"publication", "document", "evidence", "note"}


def _validate_key(value: str) -> str:
    if not _KEY_PATTERN.match(value):
        raise ValueError("key must match ^[a-z0-9][a-z0-9_-]{0,63}$")
    return value


def _validate_collection_kind(value: str) -> str:
    if value not in _VALID_COLLECTION_KINDS:
        raise ValueError(
            f"kind must be one of {sorted(_VALID_COLLECTION_KINDS)}"
        )
    return value


def _validate_item_type(value: str) -> str:
    if value not in _VALID_ITEM_TYPES:
        raise ValueError(f"item_type must be one of {sorted(_VALID_ITEM_TYPES)}")
    return value


class CollectionCreate(PersistenceSchema):
    """Payload accepted when creating a collection."""

    key: str = Field(min_length=1, max_length=64)
    title: str = Field(default="", max_length=512)
    description: str = Field(default="", max_length=4096)
    kind: str = Field(default="manual", max_length=32)
    project_id: int | None = Field(default=None, ge=1)
    filter_json: str | None = None

    @field_validator("key")
    @classmethod
    def _check_key(cls, value: str) -> str:
        return _validate_key(value)

    @field_validator("kind")
    @classmethod
    def _check_kind(cls, value: str) -> str:
        return _validate_collection_kind(value)

    def model_post_init(self, __context) -> None:
        if self.kind == "project" and self.project_id is None:
            raise ValueError("project_id is required for project-linked collections")
        if self.kind != "project" and self.project_id is not None:
            raise ValueError(
                "project_id is only valid for project-linked collections"
            )


class CollectionUpdate(PersistenceSchema):
    """Payload accepted when updating a collection."""

    title: str | None = Field(default=None, max_length=512)
    description: str | None = Field(default=None, max_length=4096)
    filter_json: str | None = None


class CollectionRead(PersistenceSchema):
    """Payload returned when reading a collection."""

    id: int
    key: str
    title: str
    description: str
    kind: str
    project_id: int | None
    filter_json: str | None
    created_at: dt.datetime
    updated_at: dt.datetime
    version: int


class CollectionItemCreate(PersistenceSchema):
    """Payload accepted when adding an item to a collection."""

    collection_id: int = Field(ge=1)
    item_type: str = Field(max_length=32)
    item_identifier: str = Field(min_length=1, max_length=128)
    note: str = Field(default="", max_length=2048)
    position: int = Field(default=0, ge=0)

    @field_validator("item_type")
    @classmethod
    def _check_item_type(cls, value: str) -> str:
        return _validate_item_type(value)


class CollectionItemUpdate(PersistenceSchema):
    """Payload accepted when updating a collection item."""

    note: str | None = Field(default=None, max_length=2048)
    position: int | None = Field(default=None, ge=0)


class CollectionItemRead(PersistenceSchema):
    """Payload returned when reading a collection item."""

    id: int
    collection_id: int
    item_type: str
    item_identifier: str
    note: str
    position: int
    created_at: dt.datetime
    updated_at: dt.datetime