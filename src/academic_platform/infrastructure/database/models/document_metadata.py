"""Document metadata model.

Extracted metadata is stored separately from the asset itself so that
metadata can be replaced without touching the asset record and so that
metadata extraction can fail without marking the asset as failed.

Design decisions
----------------
- One row per document asset. The unique constraint on ``document_id``
  enforces this.
- Optional bibliographic fields are nullable. Their absence is
  informative: a document with no DOI is not an error.
- ``authors_json`` stores an ordered list of author strings as JSON.
  Authors are not normalized; the application stores them as the
  extraction produced them and normalizes on display.
- ``extraction_confidence`` is a float between 0 and 1. It records the
  extraction pipeline's own confidence in the metadata it produced. A
  low value signals that the user should review and correct the values.
- ``reviewed_by_user`` records whether the user has confirmed the
  metadata. Unreviewed metadata is not treated as authoritative.
"""

from __future__ import annotations

from sqlalchemy import CheckConstraint, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from academic_platform.infrastructure.database.base import Base, TimestampMixin


class DocumentMetadata(Base, TimestampMixin):
    """Extracted metadata for a document asset."""

    __tablename__ = "document_metadata"
    __table_args__ = (
        CheckConstraint(
            "extraction_confidence IS NULL OR "
            "(extraction_confidence >= 0.0 AND extraction_confidence <= 1.0)",
            name="extraction_confidence_range",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("document_asset.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    title: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    authors_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    year: Mapped[int | None] = mapped_column(nullable=True)
    venue: Mapped[str | None] = mapped_column(String(512), nullable=True)
    doi: Mapped[str | None] = mapped_column(String(255), nullable=True)
    abstract: Mapped[str | None] = mapped_column(Text, nullable=True)
    language: Mapped[str | None] = mapped_column(String(16), nullable=True)
    extraction_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    extraction_method: Mapped[str] = mapped_column(
        String(64), nullable=False, default="pdf_heuristic", server_default="pdf_heuristic"
    )
    reviewed_by_user: Mapped[int] = mapped_column(
        nullable=False, default=0, server_default="0"
    )

    def __repr__(self) -> str:
        return f"<DocumentMetadata document_id={self.document_id} title={self.title!r}>"