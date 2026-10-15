"""Collection model.

A collection groups related research materials. Collections may be:

- Manual: the user adds items explicitly.
- Topic-based: assembled from a saved search or topic.
- Project-linked: associated with a single research project.
- Smart: assembled from a saved filter description.

The ``kind`` column records which of these the collection is. The
``project_id`` column is nullable; it is set for project-linked
collections and left NULL for others.

Design decisions
----------------
- The ``filter_json`` column stores the smart-collection filter as a
  JSON-encoded text value. The application evaluates the filter; the
  database does not query inside it.
- A check constraint ensures that project-linked collections carry a
  project identifier and that other kinds do not. This prevents
  inconsistent state without requiring application-level enforcement.
"""

from __future__ import annotations

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from academic_platform.infrastructure.database.base import (
    Base,
    TimestampMixin,
    VersionMixin,
)

_COLLECTION_KINDS = (
    "manual",
    "topic",
    "project",
    "saved_search",
    "smart",
)

_KIND_CHECK = "kind IN (" + ", ".join(f"'{value}'" for value in _COLLECTION_KINDS) + ")"

# Project-linked collections must have a project identifier; other kinds
# must not. This prevents an inconsistent assignment at the schema level.
_PROJECT_LINK_CHECK = (
    "(kind = 'project' AND project_id IS NOT NULL) "
    "OR (kind <> 'project' AND project_id IS NULL)"
)


class Collection(Base, TimestampMixin, VersionMixin):
    """A collection of research materials."""

    __tablename__ = "collection"
    __table_args__ = (
        CheckConstraint(_KIND_CHECK, name="kind_valid"),
        CheckConstraint(_PROJECT_LINK_CHECK, name="project_link_valid"),
        Index("ix_collection_kind", "kind"),
        Index("ix_collection_project_id", "project_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    description: Mapped[str] = mapped_column(String(4096), nullable=False, default="")
    kind: Mapped[str] = mapped_column(
        String(32), nullable=False, default="manual", server_default="manual"
    )
    project_id: Mapped[int | None] = mapped_column(
        ForeignKey("research_project.id", ondelete="CASCADE"),
        nullable=True,
    )
    filter_json: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Optional JSON-encoded filter for smart and saved-search collections.",
    )

    def __repr__(self) -> str:
        return f"<Collection key={self.key!r} kind={self.kind!r}>"