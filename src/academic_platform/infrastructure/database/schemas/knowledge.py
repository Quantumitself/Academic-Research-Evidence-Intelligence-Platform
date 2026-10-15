"""Pydantic schemas for the knowledge node and relationship models."""

from __future__ import annotations

import datetime as dt

from pydantic import Field, field_validator

from academic_platform.infrastructure.database.schemas._base import PersistenceSchema

_VALID_NODE_KINDS = {
    "topic",
    "concept",
    "theory",
    "author",
    "publication",
    "research_question",
    "variable",
    "instrument",
    "project",
    "collection",
}
_VALID_RELATIONSHIP_KINDS = {
    "studies",
    "extends",
    "challenges",
    "uses",
    "measures",
    "cites",
    "relates_to",
    "contradicts",
    "belongs_to",
}
_VALID_GROUNDINGS = {"metadata", "user_link", "ai_proposed"}


def _validate_node_kind(value: str) -> str:
    if value not in _VALID_NODE_KINDS:
        raise ValueError(f"node_kind must be one of {sorted(_VALID_NODE_KINDS)}")
    return value


def _validate_relationship_kind(value: str) -> str:
    if value not in _VALID_RELATIONSHIP_KINDS:
        raise ValueError(
            f"relationship_kind must be one of {sorted(_VALID_RELATIONSHIP_KINDS)}"
        )
    return value


def _validate_grounding(value: str) -> str:
    if value not in _VALID_GROUNDINGS:
        raise ValueError(
            f"grounding must be one of {sorted(_VALID_GROUNDINGS)}"
        )
    return value


class KnowledgeNodeCreate(PersistenceSchema):
    """Payload accepted when creating a knowledge node."""

    key: str = Field(min_length=1, max_length=128)
    node_kind: str = Field(max_length=32)
    label: str = Field(default="", max_length=512)
    description: str | None = None
    external_reference: str | None = Field(default=None, max_length=512)
    metadata_json: str | None = None

    @field_validator("node_kind")
    @classmethod
    def _check_kind(cls, value: str) -> str:
        return _validate_node_kind(value)


class KnowledgeNodeUpdate(PersistenceSchema):
    """Payload accepted when updating a knowledge node."""

    label: str | None = Field(default=None, max_length=512)
    description: str | None = None
    external_reference: str | None = Field(default=None, max_length=512)
    metadata_json: str | None = None


class KnowledgeNodeRead(PersistenceSchema):
    """Payload returned when reading a knowledge node."""

    id: int
    key: str
    node_kind: str
    label: str
    description: str | None
    external_reference: str | None
    metadata_json: str | None
    created_at: dt.datetime
    updated_at: dt.datetime
    version: int


class KnowledgeRelationshipCreate(PersistenceSchema):
    """Payload accepted when creating a knowledge relationship."""

    source_node_id: int = Field(ge=1)
    target_node_id: int = Field(ge=1)
    relationship_kind: str = Field(max_length=32)
    grounding: str = Field(default="metadata", max_length=32)
    note: str = ""

    @field_validator("relationship_kind")
    @classmethod
    def _check_kind(cls, value: str) -> str:
        return _validate_relationship_kind(value)

    @field_validator("grounding")
    @classmethod
    def _check_grounding(cls, value: str) -> str:
        return _validate_grounding(value)


class KnowledgeRelationshipRead(PersistenceSchema):
    """Payload returned when reading a knowledge relationship."""

    id: int
    source_node_id: int
    target_node_id: int
    relationship_kind: str
    grounding: str
    note: str
    created_at: dt.datetime
    updated_at: dt.datetime
    version: int