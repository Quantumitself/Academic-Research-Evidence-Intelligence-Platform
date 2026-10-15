"""Annotation and bookmark models.

Annotations and bookmarks are stored as separate records linked to a
document and its page or text location. The original PDF is never
modified to store user annotations.

Design decisions
----------------
- Annotations and bookmarks share a table so that a single query returns
  every user-authored record for a document and so that a single
  repository serves both. The ``kind`` column distinguishes them.
- Location is expressed with a nullable page number, a nullable text
  excerpt, and an optional anchor string. The anchor is opaque to the
  database; the reader interprets it.
- ``color`` is a short string (``yellow``, ``green``, ``blue``, ``pink``)
  for highlights. It is nullable for annotations that do not carry a
  color.
- Annotations and bookmarks are owned by the document. Deleting a
  document cascades to its annotations.
"""

from __future__ import annotations

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from academic_platform.infrastructure.database.base import (
    Base,
    TimestampMixin,
    VersionMixin,
)

_KINDS = ("note", "highlight", "bookmark")
_KIND_CHECK = "kind IN (" + ", ".join(f"'{value}'" for value in _KINDS) + ")"

_COLORS = ("yellow", "green", "blue", "pink")
_COLOR_CHECK = (
    "color IS NULL OR color IN ("
    + ", ".join(f"'{value}'" for value in _COLORS)
    + ")"
)


class Annotation(Base, TimestampMixin, VersionMixin):
    """A user-authored note, highlight, or bookmark on a document."""

    __tablename__ = "annotation"
    __table_args__ = (
        CheckConstraint(_KIND_CHECK, name="kind_valid"),
        CheckConstraint(_COLOR_CHECK, name="color_valid"),
        Index("ix_annotation_document_page", "document_id", "page_number"),
        Index("ix_annotation_document_kind", "document_id", "kind"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("document_asset.id", ondelete="CASCADE"),
        nullable=False,
    )
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    page_number: Mapped[int | None] = mapped_column(nullable=True)
    text_excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    anchor: Mapped[str | None] = mapped_column(String(255), nullable=True)
    color: Mapped[str | None] = mapped_column(String(16), nullable=True)

    def __repr__(self) -> str:
        return (
            f"<Annotation document_id={self.document_id} "
            f"kind={self.kind!r} page={self.page_number}>"
        )