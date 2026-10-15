"""Collection item model.

A collection item is an association between a collection and a resource.
The resource is identified by a typed reference: ``item_type`` names the
kind of resource (publication, document, evidence record, note) and
``item_identifier`` names the specific resource within that type.

Design decisions
----------------
- The association is modeled as a first-class entity rather than as a
  many-to-many table because items carry ordering and an optional note.
  A pure association table cannot express those attributes without an
  additional table.
- ``item_type`` is a closed enumeration enforced by a check constraint.
  New resource types require a migration.
- ``item_identifier`` is a string. It holds the stable string identifier
  of the referenced resource (the ``key`` of a publication, the UUID of
  an imported document, and so on). The application layer resolves the
  identifier to the resource.
- The unique constraint on ``(collection_id, item_type, item_identifier)``
  prevents the same resource from being added twice to the same
  collection.
"""

from __future__ import annotations

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from academic_platform.infrastructure.database.base import Base, TimestampMixin

_ITEM_TYPES = (
    "publication",
    "document",
    "evidence",
    "note",
)

_ITEM_TYPE_CHECK = (
    "item_type IN (" + ", ".join(f"'{value}'" for value in _ITEM_TYPES) + ")"
)


class CollectionItem(Base, TimestampMixin):
    """Association between a collection and a resource."""

    __tablename__ = "collection_item"
    __table_args__ = (
        CheckConstraint(_ITEM_TYPE_CHECK, name="item_type_valid"),
        UniqueConstraint(
            "collection_id",
            "item_type",
            "item_identifier",
            name="uq_collection_item_target",
        ),
        Index("ix_collection_item_collection_position", "collection_id", "position"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    collection_id: Mapped[int] = mapped_column(
        ForeignKey("collection.id", ondelete="CASCADE"),
        nullable=False,
    )
    item_type: Mapped[str] = mapped_column(String(32), nullable=False)
    item_identifier: Mapped[str] = mapped_column(String(128), nullable=False)
    note: Mapped[str] = mapped_column(String(2048), nullable=False, default="")
    position: Mapped[int] = mapped_column(nullable=False, default=0, server_default="0")

    def __repr__(self) -> str:
        return (
            f"<CollectionItem collection={self.collection_id} "
            f"type={self.item_type!r} identifier={self.item_identifier!r}>"
        )