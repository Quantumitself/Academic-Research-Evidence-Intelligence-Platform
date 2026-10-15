"""Research guide, section, and citation models.

A research guide is a structured learning or research document generated
from a topic, project, collection, or selected papers. Guides are
composed of ordered sections. Source-derived statements carry citations
that link them to the specific source records they reference.

Design decisions
----------------
- A guide is owned by an optional project or collection. When the owner
  is deleted, the guide is preserved but its owner reference is cleared;
  the guide is user-authored content.
- Sections are ordered within a guide by the ``position`` column.
- Sections carry their own body text and an optional list of reading
  references. A section may include both source-derived and general
  statements; source-derived statements carry citations, general
  statements do not.
- Citations link a section to a typed source. The source may be a
  publication, a document, an evidence record, or an external URL.
- Citations record the quoted or paraphrased text so that the claim can
  be verified without re-extracting the source.
"""

from __future__ import annotations

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from academic_platform.infrastructure.database.base import (
    Base,
    TimestampMixin,
    VersionMixin,
)

_GUIDE_KINDS = ("topic", "project", "collection", "papers")
_GUIDE_KIND_CHECK = (
    "guide_kind IN (" + ", ".join(f"'{value}'" for value in _GUIDE_KINDS) + ")"
)

_CITATION_SOURCE_TYPES = ("publication", "document", "evidence", "external")
_CITATION_SOURCE_CHECK = (
    "source_type IN ("
    + ", ".join(f"'{value}'" for value in _CITATION_SOURCE_TYPES)
    + ")"
)


class ResearchGuide(Base, TimestampMixin, VersionMixin):
    """A structured research or learning guide."""

    __tablename__ = "research_guide"
    __table_args__ = (
        CheckConstraint(_GUIDE_KIND_CHECK, name="guide_kind_valid"),
        Index("ix_research_guide_owner_project", "project_id"),
        Index("ix_research_guide_owner_collection", "collection_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, index=True
    )
    title: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    guide_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    topic: Mapped[str] = mapped_column(String(1024), nullable=False, default="")
    project_id: Mapped[int | None] = mapped_column(
        ForeignKey("research_project.id", ondelete="SET NULL"),
        nullable=True,
    )
    collection_id: Mapped[int | None] = mapped_column(
        ForeignKey("collection.id", ondelete="SET NULL"),
        nullable=True,
    )
    overview: Mapped[str] = mapped_column(Text, nullable=False, default="")
    generated_by: Mapped[str] = mapped_column(
        String(32), nullable=False, default="user", server_default="user"
    )

    def __repr__(self) -> str:
        return f"<ResearchGuide key={self.key!r} kind={self.guide_kind!r}>"


class ResearchGuideSection(Base, TimestampMixin):
    """A single ordered section of a research guide."""

    __tablename__ = "research_guide_section"
    __table_args__ = (
        Index("ix_research_guide_section_guide_position", "guide_id", "position"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    guide_id: Mapped[int] = mapped_column(
        ForeignKey("research_guide.id", ondelete="CASCADE"),
        nullable=False,
    )
    heading: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    position: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    is_source_derived: Mapped[int] = mapped_column(
        nullable=False, default=0, server_default="0"
    )

    def __repr__(self) -> str:
        return (
            f"<ResearchGuideSection guide={self.guide_id} "
            f"position={self.position} heading={self.heading!r}>"
        )


class CitationRecord(Base, TimestampMixin):
    """A citation linking a guide section to a source."""

    __tablename__ = "citation_record"
    __table_args__ = (
        CheckConstraint(_CITATION_SOURCE_CHECK, name="source_type_valid"),
        Index("ix_citation_record_section", "section_id"),
        Index("ix_citation_record_source", "source_type", "source_identifier"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    section_id: Mapped[int] = mapped_column(
        ForeignKey("research_guide_section.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_type: Mapped[str] = mapped_column(String(16), nullable=False)
    source_identifier: Mapped[str] = mapped_column(String(255), nullable=False)
    quoted_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    note: Mapped[str] = mapped_column(Text, nullable=False, default="")

    def __repr__(self) -> str:
        return (
            f"<CitationRecord section={self.section_id} "
            f"source={self.source_type}:{self.source_identifier}>"
        )