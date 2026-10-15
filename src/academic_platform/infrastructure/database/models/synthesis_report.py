"""Synthesis report model.

A synthesis report is a source-linked narrative produced by the evidence
synthesis workflow. It records which runs contributed, which studies were
included and excluded, the narrative itself, and any limitations. Reports
are versioned so that successive runs can be compared.

Design decisions
----------------
- The report stores the narrative text as a single column. The narrative
  is the primary output; structured detail (included studies, excluded
  studies, limitations) is stored in the JSON columns.
- ``report_kind`` is a closed enumeration: ``narrative``,
  ``meta_analysis``, ``mixed``.
- ``contributing_run_ids_json`` records the analysis runs the report
  references. It is populated even for narrative reports that did not
  execute a statistical analysis, so that the report's provenance is
  complete.
- ``included_evidence_ids_json`` and ``excluded_evidence_ids_json``
  record the specific evidence records that were included or excluded
  and why. The exclusion reasons are stored in
  ``exclusion_reasons_json``.
- The report is versioned; successive runs create new rows. The report
  for a given collection can be retrieved by filtering on the collection
  identifier and ordering by creation time.
"""

from __future__ import annotations

from sqlalchemy import CheckConstraint, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import ForeignKey

from academic_platform.infrastructure.database.base import (
    Base,
    TimestampMixin,
    VersionMixin,
)

_REPORT_KINDS = ("narrative", "meta_analysis", "mixed")
_REPORT_KIND_CHECK = (
    "report_kind IN (" + ", ".join(f"'{v}'" for v in _REPORT_KINDS) + ")"
)


class SynthesisReport(Base, TimestampMixin, VersionMixin):
    """A source-linked synthesis report."""

    __tablename__ = "synthesis_report"
    __table_args__ = (
        CheckConstraint(_REPORT_KIND_CHECK, name="report_kind_valid"),
        Index("ix_synthesis_report_collection", "collection_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    collection_id: Mapped[int | None] = mapped_column(
        ForeignKey("collection.id", ondelete="CASCADE"),
        nullable=True,
    )
    report_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    narrative: Mapped[str] = mapped_column(Text, nullable=False, default="")
    contributing_run_ids_json: Mapped[str] = mapped_column(
        Text, nullable=False, default="[]", server_default="[]"
    )
    included_evidence_ids_json: Mapped[str] = mapped_column(
        Text, nullable=False, default="[]", server_default="[]"
    )
    excluded_evidence_ids_json: Mapped[str] = mapped_column(
        Text, nullable=False, default="[]", server_default="[]"
    )
    exclusion_reasons_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    limitations_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    reproducibility_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return (
            f"<SynthesisReport id={self.id} kind={self.report_kind!r} "
            f"collection={self.collection_id}>"
        )