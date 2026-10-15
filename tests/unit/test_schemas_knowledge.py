"""Tests for the knowledge Pydantic schemas."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from academic_platform.infrastructure.database.schemas import (
    KnowledgeNodeCreate,
    KnowledgeRelationshipCreate,
)


def test_node_create_defaults() -> None:
    payload = KnowledgeNodeCreate(key="topic:x", node_kind="topic")
    assert payload.label == ""


def test_node_create_rejects_bad_kind() -> None:
    with pytest.raises(ValidationError):
        KnowledgeNodeCreate(key="topic:x", node_kind="bogus")


def test_relationship_create_defaults() -> None:
    payload = KnowledgeRelationshipCreate(
        source_node_id=1,
        target_node_id=2,
        relationship_kind="relates_to",
    )
    assert payload.grounding == "metadata"


def test_relationship_create_rejects_bad_kind() -> None:
    with pytest.raises(ValidationError):
        KnowledgeRelationshipCreate(
            source_node_id=1,
            target_node_id=2,
            relationship_kind="bogus",
        )


def test_relationship_create_rejects_bad_grounding() -> None:
    with pytest.raises(ValidationError):
        KnowledgeRelationshipCreate(
            source_node_id=1,
            target_node_id=2,
            relationship_kind="relates_to",
            grounding="bogus",
        )