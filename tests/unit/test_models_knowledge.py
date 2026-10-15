"""Tests for the knowledge node and relationship models."""

from __future__ import annotations

import pytest

from academic_platform.infrastructure.database import DatabaseError

from academic_platform.infrastructure.database import Database
from academic_platform.infrastructure.database.base import Base
from academic_platform.infrastructure.database.models import (
    KnowledgeNode,
    KnowledgeRelationship,
)


@pytest.fixture()
def database() -> Database:
    db = Database.in_memory()
    Base.metadata.create_all(db.engine)
    yield db
    db.dispose()


def test_create_node(database: Database) -> None:
    with database.session() as session:
        node = KnowledgeNode(key="topic:x", node_kind="topic", label="X")
        session.add(node)
        session.flush()
        identifier = node.id
    with database.session() as session:
        loaded = session.get(KnowledgeNode, identifier)
        assert loaded is not None
        assert loaded.label == "X"


def test_invalid_node_kind_rejected(database: Database) -> None:
    with pytest.raises(DatabaseError):
        with database.session() as session:
            session.add(KnowledgeNode(key="x", node_kind="bogus"))


def test_edge_unique(database: Database) -> None:
    with database.session() as session:
        a = KnowledgeNode(key="a", node_kind="topic")
        b = KnowledgeNode(key="b", node_kind="concept")
        session.add_all([a, b])
        session.flush()
        session.add(
            KnowledgeRelationship(
                source_node_id=a.id,
                target_node_id=b.id,
                relationship_kind="relates_to",
            )
        )
    with pytest.raises(DatabaseError):
        with database.session() as session:
            session.add(
                KnowledgeRelationship(
                    source_node_id=1,
                    target_node_id=2,
                    relationship_kind="relates_to",
                )
            )


def test_invalid_relationship_kind_rejected(database: Database) -> None:
    with database.session() as session:
        a = KnowledgeNode(key="a", node_kind="topic")
        b = KnowledgeNode(key="b", node_kind="concept")
        session.add_all([a, b])
        session.flush()
    with pytest.raises(DatabaseError):
        with database.session() as session:
            session.add(
                KnowledgeRelationship(
                    source_node_id=1,
                    target_node_id=2,
                    relationship_kind="bogus",
                )
            )


def test_invalid_grounding_rejected(database: Database) -> None:
    with database.session() as session:
        a = KnowledgeNode(key="a", node_kind="topic")
        b = KnowledgeNode(key="b", node_kind="concept")
        session.add_all([a, b])
        session.flush()
    with pytest.raises(DatabaseError):
        with database.session() as session:
            session.add(
                KnowledgeRelationship(
                    source_node_id=1,
                    target_node_id=2,
                    relationship_kind="relates_to",
                    grounding="bogus",
                )
            )