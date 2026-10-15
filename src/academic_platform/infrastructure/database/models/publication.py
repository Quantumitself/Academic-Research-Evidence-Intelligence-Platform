"""Publication model.

A publication represents a scholarly work retrieved from a remote source
or created from a bibliographic identifier. It stores the normalized
bibliographic fields the application uses across search, library, and
evidence workflows.

Design decisions
----------------
- The DOI is stored in a dedicated column and is unique when present.
  Most publications come from sources that provide a DOI. A publication
  without a DOI is permitted; the application falls back to a stable key
  derived from the source metadata.
- ``source_providers_json`` stores the list of provider identifiers that
  returned the publication. The list is populated on first insert and
  extended when the same publication is returned by another provider.
- ``abstract`` is stored as-is. The application never modifies the
  abstract; normalization belongs to presentation.
- The publication's ``key`` is a stable, human-readable identifier used
  in collection items, audit events, and external references. It is
  constructed by the application from the DOI or from the source
  identifier.
"""

from __future__ import annotations

from sqlalchemy import Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from academic_platform.infrastructure.database.base import (
    Base,
    TimestampMixin,
    VersionMixin,
)


class Publication(Base, TimestampMixin, VersionMixin):
    """A scholarly publication."""

    __tablename__ = "publication"
    __table_args__ = (
        Index("ix_publication_year", "year"),
        Index("ix_publication_title", "title"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    doi: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True)
    title: Mapped[str] = mapped_column(String(2048), nullable=False, default="")
    authors_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    venue: Mapped[str | None] = mapped_column(String(512), nullable=True)
    abstract: Mapped[str | None] = mapped_column(Text, nullable=True)
    language: Mapped[str | None] = mapped_column(String(16), nullable=True)
    is_open_access: Mapped[int] = mapped_column(
        nullable=False, default=0, server_default="0"
    )
    citation_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_providers_json: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="[]",
        server_default="[]",
        doc="JSON list of provider identifiers that returned this publication.",
    )
    url: Mapped[str | None] = mapped_column(String(2048), nullable=True)

    def __repr__(self) -> str:
        return f"<Publication key={self.key!r} year={self.year}>"