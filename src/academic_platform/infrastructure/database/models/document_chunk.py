"""Document chunk model.

Extracted text is stored in chunks so that the reader can navigate large
documents without loading their full content into memory and so that
the full-text index can be updated incrementally.

Design decisions
----------------
- Each chunk carries a ``page_number`` when the extractor can attribute
  the text to a page. Some formats do not provide page information;
  ``page_number`` is then nullable.
- Each chunk carries a ``chunk_index`` that orders chunks within a
  document. The ordering is stable across re-extraction runs when the
  extractor is deterministic.
- ``content`` stores the chunk text. Chunks are bounded in size by the
  extraction pipeline; the schema does not enforce a maximum length, but
  the pipeline targets a range that fits the full-text index's
  performance envelope.
- ``token_count`` is stored when the extractor can compute it. It is
  used for cost estimation and for capping AI context windows.
"""

from __future__ import annotations

from sqlalchemy import ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from academic_platform.infrastructure.database.base import Base, TimestampMixin


class DocumentChunk(Base, TimestampMixin):
    """A bounded chunk of extracted text from a document."""

    __tablename__ = "document_chunk"
    __table_args__ = (
        Index("ix_document_chunk_document_index", "document_id", "chunk_index"),
        Index("ix_document_chunk_document_page", "document_id", "page_number"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("document_asset.id", ondelete="CASCADE"),
        nullable=False,
    )
    chunk_index: Mapped[int] = mapped_column(nullable=False)
    page_number: Mapped[int | None] = mapped_column(nullable=True)
    section_title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    def __repr__(self) -> str:
        return (
            f"<DocumentChunk document_id={self.document_id} "
            f"index={self.chunk_index} page={self.page_number}>"
        )