"""Analysis run, input, and result models.

An analysis run records a single execution of the statistical engine. It
carries the analysis type, the specification inputs, the outcome, and
timing information. Inputs are stored as separate rows so that the
reproducibility record is complete: every value the engine consumed is
preserved alongside the run. Results are stored as a single JSON payload
per run because the shape of the result varies by analysis type.

Design decisions
----------------
- The run is append-only with respect to its inputs and results. Rerunning
  an analysis creates a new run. Previous runs are preserved so that the
  user can compare results and so that a support investigation can
  reconstruct what the engine consumed.
- ``status`` is a closed enumeration: ``running``, ``succeeded``,
  ``failed``, ``cancelled``.
- ``analysis_type`` is a closed enumeration matching the analysis
  functions the engine exposes: ``descriptive``, ``t_test``,
  ``correlation``, ``regression``, ``effect_size``, ``meta_analysis``,
  ``reliability``, ``other``. New analysis types require a migration and
  a corresponding engine implementation.
- ``library_versions_json`` records the versions of the numerical
  libraries that produced the result. Reproducibility requires these
  versions because numerical outputs can differ across library versions.
- ``warnings_json`` records any warnings the engine emitted. Warnings
  are stored even when the run succeeded so that the user sees them in
  the report.
- ``result_json`` stores the analysis output. The shape is defined by the
  analysis type and is documented in the statistical-methods
  documentation.
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

_ANALYSIS_TYPES = (
    "descriptive",
    "t_test",
    "correlation",
    "regression",
    "effect_size",
    "meta_analysis",
    "reliability",
    "other",
)
_ANALYSIS_TYPE_CHECK = (
    "analysis_type IN ("
    + ", ".join(f"'{v}'" for v in _ANALYSIS_TYPES)
    + ")"
)


class AnalysisRun(Base, TimestampMixin):
    """A single execution of the statistical engine."""

    __tablename__ = "analysis_run"
    __table_args__ = (
        CheckConstraint(_STATUS_CHECK, name="status_valid"),
        CheckConstraint(_ANALYSIS_TYPE_CHECK, name="analysis_type_valid"),
        Index("ix_analysis_run_analysis_type", "analysis_type"),
        Index("ix_analysis_run_started_at", "started_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    analysis_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    started_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)
    finished_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    engine_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    library_versions_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    settings_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    warnings_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    inputs_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )

    def __repr__(self) -> str:
        return (
            f"<AnalysisRun id={self.id} type={self.analysis_type!r} "
            f"status={self.status!r}>"
        )


class AnalysisInput(Base, TimestampMixin):
    """A single input value consumed by an analysis run.

    Each row records one scalar or vector value the engine received.
    Values are stored as text; the schema of the value is recorded in
    ``value_kind`` so that the analysis runner can reconstruct the
    original type.
    """

    __tablename__ = "analysis_input"
    __table_args__ = (
        Index("ix_analysis_input_run", "analysis_run_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    analysis_run_id: Mapped[int] = mapped_column(
        ForeignKey("analysis_run.id", ondelete="CASCADE"),
        nullable=False,
    )
    input_key: Mapped[str] = mapped_column(String(128), nullable=False)
    value_kind: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        doc="One of: number, integer, string, boolean, list, null.",
    )
    value_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_evidence_id: Mapped[int | None] = mapped_column(
        ForeignKey("evidence_record.id", ondelete="SET NULL"),
        nullable=True,
    )

    def __repr__(self) -> str:
        return (
            f"<AnalysisInput run={self.analysis_run_id} key={self.input_key!r}>"
        )