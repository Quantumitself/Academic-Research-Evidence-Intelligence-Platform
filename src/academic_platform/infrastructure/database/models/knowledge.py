"""Knowledge node and relationship models.

A knowledge node represents a topic, concept, theory, author,
publication, research question, variable, instrument, project, or
collection that participates in the knowledge map. A knowledge
relationship connects two nodes with a typed edge.

Design decisions
----------------
- Nodes are identified by a stable ``key``. The key is constructed by
  the application from the node's kind and its underlying identifier
  (``topic:measurement-invariance``, ``publication:10.1000-xyz``). It is
  unique across the table.
- ``node_kind`` is a closed enumeration. New kinds require a migration.
- Relationships are directed. The combination
  ``(source_node_id, target_node_id, relationship_kind)`` is unique, so
  the same edge cannot be created twice.
- ``relationship_kind`` is a closed enumeration matching the vocabulary
  in the product specification.
- ``grounding`` records whether the relationship is grounded in metadata,
  in an explicit user link, or in an AI-proposed inference. AI-proposed
  relationships carry the ``ai_proposed`` state and are visually
  distinguished in the map until confirmed.
"""

from __future__ import annotations

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from academic_platform.infrastructure.database.base import (
    Base,
    TimestampMixin,
    VersionMixin,
)

_NODE_KINDS = (
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
)
_NODE_KIND_CHECK = (
    "node_kind IN (" + ", ".join(f"'{value}'" for value in _NODE_KINDS) + ")"
)

_RELATIONSHIP_KINDS = (
    "studies",
    "extends",
    "challenges",
    "uses",
    "measures",
    "cites",
    "relates_to",
    "contradicts",
    "belongs_to",
)
_RELATIONSHIP_KIND_CHECK = (
    "relationship_kind IN ("
    + ", ".join(f"'{value}'" for value in _RELATIONSHIP_KINDS)
    + ")"
)

_GROUNDING_STATES = ("metadata", "user_link", "ai_proposed")
_GROUNDING_CHECK = (
    "grounding IN (" + ", ".join(f"'{value}'" for value in _GROUNDING_STATES) + ")"
)


class KnowledgeNode(Base, TimestampMixin, VersionMixin):
    """A node in the knowledge map."""

    __tablename__ = "knowledge_node"
    __table_args__ = (
        CheckConstraint(_NODE_KIND_CHECK, name="node_kind_valid"),
        Index("ix_knowledge_node_kind", "node_kind"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(
        String(128), nullable=False, unique=True, index=True
    )
    node_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    label: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    external_reference: Mapped[str | None] = mapped_column(
        String(512),
        nullable=True,
        doc="Optional external identifier (DOI, ORCID, project key).",
    )
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<KnowledgeNode key={self.key!r} kind={self.node_kind!r}>"


class KnowledgeRelationship(Base, TimestampMixin, VersionMixin):
    """A directed edge between two knowledge nodes."""

    __tablename__ = "knowledge_relationship"
    __table_args__ = (
        CheckConstraint(_RELATIONSHIP_KIND_CHECK, name="relationship_kind_valid"),
        CheckConstraint(_GROUNDING_CHECK, name="grounding_valid"),
        UniqueConstraint(
            "source_node_id",
            "target_node_id",
            "relationship_kind",
            name="uq_knowledge_relationship_edge",
        ),
        Index("ix_knowledge_relationship_source", "source_node_id"),
        Index("ix_knowledge_relationship_target", "target_node_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    source_node_id: Mapped[int] = mapped_column(
        ForeignKey("knowledge_node.id", ondelete="CASCADE"),
        nullable=False,
    )
    target_node_id: Mapped[int] = mapped_column(
        ForeignKey("knowledge_node.id", ondelete="CASCADE"),
        nullable=False,
    )
    relationship_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    grounding: Mapped[str] = mapped_column(
        String(32), nullable=False, default="metadata", server_default="metadata"
    )
    note: Mapped[str] = mapped_column(Text, nullable=False, default="")

    def __repr__(self) -> str:
        return (
            f"<KnowledgeRelationship {self.source_node_id} "
            f"-{self.relationship_kind}-> {self.target_node_id}>"
        )