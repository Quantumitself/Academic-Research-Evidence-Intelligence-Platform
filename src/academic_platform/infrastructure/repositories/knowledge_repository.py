"""Repositories for the knowledge map."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from academic_platform.infrastructure.database.models import (
    KnowledgeNode,
    KnowledgeRelationship,
)
from academic_platform.infrastructure.repositories.base import Repository
from academic_platform.infrastructure.repositories.errors import RepositoryError


class KnowledgeNodeRepository(Repository[KnowledgeNode]):
    """Repository for the ``knowledge_node`` table."""

    entity = KnowledgeNode

    def find_by_key(self, key: str) -> KnowledgeNode | None:
        """Return the node with the given key, or ``None``."""
        statement = select(KnowledgeNode).where(KnowledgeNode.key == key).limit(1)
        try:
            return self._session.execute(statement).scalars().first()
        except SQLAlchemyError as exc:
            raise RepositoryError(f"find_by_key failed: {exc}") from exc

    def list_by_kind(self, node_kind: str) -> list[KnowledgeNode]:
        """Return the nodes of a specific kind ordered by label."""
        statement = (
            select(KnowledgeNode)
            .where(KnowledgeNode.node_kind == node_kind)
            .order_by(KnowledgeNode.label)
        )
        try:
            return list(self._session.execute(statement).scalars().all())
        except SQLAlchemyError as exc:
            raise RepositoryError(f"list_by_kind failed: {exc}") from exc

    def upsert_by_key(
        self,
        key: str,
        *,
        node_kind: str,
        label: str = "",
        description: str | None = None,
        external_reference: str | None = None,
        metadata_json: str | None = None,
    ) -> tuple[KnowledgeNode, bool]:
        """Create or update a node identified by its key.

        Returns ``(node, created)``. When the node already exists, only
        the supplied non-default fields are updated. The node kind is not
        changed once set; a different kind requires a new key.
        """
        existing = self.find_by_key(key)
        if existing is None:
            node = KnowledgeNode(
                key=key,
                node_kind=node_kind,
                label=label,
                description=description,
                external_reference=external_reference,
                metadata_json=metadata_json,
            )
            return self.add(node), True
        if label:
            existing.label = label
        if description is not None:
            existing.description = description
        if external_reference is not None:
            existing.external_reference = external_reference
        if metadata_json is not None:
            existing.metadata_json = metadata_json
        try:
            self._session.flush()
        except SQLAlchemyError as exc:
            raise RepositoryError(f"upsert_by_key failed: {exc}") from exc
        return existing, False


class KnowledgeRelationshipRepository(Repository[KnowledgeRelationship]):
    """Repository for the ``knowledge_relationship`` table."""

    entity = KnowledgeRelationship

    def list_from(self, source_node_id: int) -> list[KnowledgeRelationship]:
        """Return relationships whose source is the given node."""
        statement = select(KnowledgeRelationship).where(
            KnowledgeRelationship.source_node_id == source_node_id
        )
        try:
            return list(self._session.execute(statement).scalars().all())
        except SQLAlchemyError as exc:
            raise RepositoryError(f"list_from failed: {exc}") from exc

    def list_to(self, target_node_id: int) -> list[KnowledgeRelationship]:
        """Return relationships whose target is the given node."""
        statement = select(KnowledgeRelationship).where(
            KnowledgeRelationship.target_node_id == target_node_id
        )
        try:
            return list(self._session.execute(statement).scalars().all())
        except SQLAlchemyError as exc:
            raise RepositoryError(f"list_to failed: {exc}") from exc

    def find_edge(
        self,
        source_node_id: int,
        target_node_id: int,
        relationship_kind: str,
    ) -> KnowledgeRelationship | None:
        """Return the specific edge, or ``None`` when it does not exist."""
        statement = (
            select(KnowledgeRelationship)
            .where(
                KnowledgeRelationship.source_node_id == source_node_id,
                KnowledgeRelationship.target_node_id == target_node_id,
                KnowledgeRelationship.relationship_kind == relationship_kind,
            )
            .limit(1)
        )
        try:
            return self._session.execute(statement).scalars().first()
        except SQLAlchemyError as exc:
            raise RepositoryError(f"find_edge failed: {exc}") from exc

    def add_edge(
        self,
        source_node_id: int,
        target_node_id: int,
        relationship_kind: str,
        *,
        grounding: str = "metadata",
        note: str = "",
    ) -> KnowledgeRelationship:
        """Create an edge, or return the existing one when identical."""
        existing = self.find_edge(source_node_id, target_node_id, relationship_kind)
        if existing is not None:
            return existing
        relationship = KnowledgeRelationship(
            source_node_id=source_node_id,
            target_node_id=target_node_id,
            relationship_kind=relationship_kind,
            grounding=grounding,
            note=note,
        )
        return self.add(relationship)