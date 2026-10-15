"""Evidence extraction run model.

An evidence extraction run records a single execution of the extraction
pipeline over a document. It carries the pipeline version, the
extraction method used, the outcome, and timing information. Evidence
records reference the run that produced them so that the entire
extraction session is traceable.

Design decisions
----------------
- The run is append-only. Rerunning extraction on the same document
  creates a new run; the previous run and its records are preserved so
  that the user can compare runs or revert to an earlier extraction.
- ``status`` is a closed enumeration: ``running``, ``succeeded``,
  ``failed``, ``cancelled``. Running runs are permitted so that a crash
  during extraction leaves a diagnostic record.
- ``method`` records the extraction method: ``rule_based``,
  ``ai_assisted``, ``hybrid``. The set is closed.
- ``ai_provider_snapshot`` and ``ai_model_snapshot`` record the provider
  and model used, when the run used AI assistance. They are nullable for
  rule-based runs.
- ``parameters_json`` stores run-specific parameters such as the
  extraction version and any toggles the user applied.
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from academic_platform.infrastructure.database.base import Base, TimestampMixin

_STATUSES = ("running", "succeeded", "failed", "cancelled")
_STATUS_CHECK = "status IN (" + ", ".join(f"'{v}'" for v in _STATUSES) + ")"

_METHODS = ("rule_based", "ai_assisted", "hybrid")
_METHOD_CHECK = "method IN (" + ", ".join(f"'{v}'" for v in _METHODS) + ")"


class EvidenceExtractionRun(Base, TimestampMixin):
    """A single execution of the evidence extraction pipeline."""

    __tablename__ = "evidence_extraction_run"
    __table_args__ = (
        CheckConstraint(_STATUS_CHECK, name="status_valid"),
        CheckConstraint(_METHOD_CHECK, name="method_valid"),
        Index("ix_evidence_extraction_run_document", "document_id"),
        Index("ix_evidence_extraction_run_started_at", "started_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("document_asset.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    method: Mapped[str] = mapped_column(String(16), nullable=False)
    pipeline_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    started_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)
    finished_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ai_provider_snapshot: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    ai_model_snapshot: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    parameters_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    records_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )

    def __repr__(self) -> str:
        return (
            f"<EvidenceExtractionRun id={self.id} "
            f"document={self.document_id} status={self.status!r}>"
        )