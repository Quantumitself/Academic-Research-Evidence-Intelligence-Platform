"""Tests for the knowledge repositories."""

from __future__ import annotations

import pytest

from academic_platform.infrastructure.database import Database
from academic_platform.infrastructure.database.base import Base
from academic_platform.infrastructure.database.models import (
    KnowledgeNode,
)
from academic_platform.infrastructure.database.schemas import (
    KnowledgeNodeCreate,
    KnowledgeRelationshipCreate,
)
from academic_platform.infrastructure.repositories.knowledge_repository import (
    KnowledgeNodeRepository,
    KnowledgeRelationshipRepository,
)


@pytest.fixture()
def database() -> Database:
    db = Database.in_memory()
    Base.metadata.create_all(db.engine)
    yield db
    db.dispose()


def test_upsert_by_key_creates_then_updates(database: Database) -> None:
    with database.session() as session:
        repo = KnowledgeNodeRepository(session)
        node, created = repo.upsert_by_key(
            "topic:x", node_kind="topic", label="X"
        )
        assert created is True
        node_id = node.id
    with database.session() as session:
        repo = KnowledgeNodeRepository(session)
        node, created = repo.upsert_by_key(
            "topic:x", node_kind="topic", label="Updated"
        )
        assert created is False
        assert node.id == node_id
        assert node.label == "Updated"


def test_list_by_kind(database: Database) -> None:
    with database.session() as session:
        repo = KnowledgeNodeRepository(session)
        repo.create(KnowledgeNodeCreate(key="topic:a", node_kind="topic", label="A"))
        repo.create(KnowledgeNodeCreate(key="topic:b", node_kind="topic", label="B"))
        repo.create(KnowledgeNodeCreate(key="concept:c", node_kind="concept"))
    with database.session() as session:
        repo = KnowledgeNodeRepository(session)
        topics = repo.list_by_kind("topic")
        assert [n.label for n in topics] == ["A", "B"]


def test_relationship_add_and_list(database: Database) -> None:
    with database.session() as session:
        node_repo = KnowledgeNodeRepository(session)
        rel_repo = KnowledgeRelationshipRepository(session)
        a = node_repo.create(KnowledgeNodeCreate(key="a", node_kind="topic"))
        b = node_repo.create(KnowledgeNodeCreate(key="b", node_kind="concept"))
        rel_repo.create(
            KnowledgeRelationshipCreate(
                source_node_id=a.id,
                target_node_id=b.id,
                relationship_kind="relates_to",
            )
        )
    with database.session() as session:
        rel_repo = KnowledgeRelationshipRepository(session)
        edges = rel_repo.list_from(1)
        assert len(edges) == 1


def test_add_edge_is_idempotent(database: Database) -> None:
    with database.session() as session:
        node_repo = KnowledgeNodeRepository(session)
        rel_repo = KnowledgeRelationshipRepository(session)
        a = node_repo.create(KnowledgeNodeCreate(key="a", node_kind="topic"))
        b = node_repo.create(KnowledgeNodeCreate(key="b", node_kind="concept"))
        first = rel_repo.add_edge(a.id, b.id, "relates_to")
        second = rel_repo.add_edge(a.id, b.id, "relates_to")
        assert first.id == second.id