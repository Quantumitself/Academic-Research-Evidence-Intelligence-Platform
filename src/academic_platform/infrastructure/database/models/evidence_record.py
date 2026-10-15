"""Evidence record model.

An evidence record represents a single structured fact extracted from a
document: a study design, a population, a sample size, a measurement, an
effect estimate, a confidence interval, or similar. Records are owned by
a document and, when applicable, by the extraction run that produced
them.

Design decisions
----------------
- A record carries both the extracted value and the raw source text from
  which it was extracted. The raw text preserves provenance so that a
  reviewer can verify the extraction against the source.
- ``verification_status`` is a closed enumeration that records the
  extraction pipeline's state and the user's review state:
  ``ai_proposed``, ``auto_parsed``, ``user_verified``, ``uncertain``,
  ``rejected``, ``missing``.
- ``extraction_method`` records how the value was produced:
  ``rule_based``, ``ai_assisted``, ``user_entered``. This preserves the
  distinction between deterministic extraction and AI-assisted proposals.
- ``normalized_value_json`` stores the value after unit conversion or
  effect-direction alignment. The original value is preserved in
  ``reported_value_json``. Both are stored as JSON.
- ``page_number`` and ``section_title`` record where in the document the
  extraction came from. They are nullable because some extraction
  methods cannot attribute text to a page.
- ``evidence_type`` is a closed enumeration: ``study_design``,
  ``population``, ``sample_size``, ``measurement``, ``group_statistic``,
  ``effect_estimate``, ``p_value``, ``confidence_interval``,
  ``covariate``, ``limitation``, ``outcome_definition``, ``other``.
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

_EVIDENCE_TYPES = (
    "study_design",
    "population",
    "sample_size",
    "measurement",
    "group_statistic",
    "effect_estimate",
    "p_value",
    "confidence_interval",
    "covariate",
    "limitation",
    "outcome_definition",
    "other",
)
_EVIDENCE_TYPE_CHECK = (
    "evidence_type IN ("
    + ", ".join(f"'{value}'" for value in _EVIDENCE_TYPES)
    + ")"
)

_VERIFICATION_STATES = (
    "ai_proposed",
    "auto_parsed",
    "user_verified",
    "uncertain",
    "rejected",
    "missing",
)
_VERIFICATION_CHECK = (
    "verification_status IN ("
    + ", ".join(f"'{value}'" for value in _VERIFICATION_STATES)
    + ")"
)

_EXTRACTION_METHODS = ("rule_based", "ai_assisted", "user_entered")
_EXTRACTION_CHECK = (
    "extraction_method IN ("
    + ", ".join(f"'{value}'" for value in _EXTRACTION_METHODS)
    + ")"
)


class EvidenceRecord(Base, TimestampMixin, VersionMixin):
    """A structured fact extracted from a document."""

    __tablename__ = "evidence_record"
    __table_args__ = (
        CheckConstraint(_EVIDENCE_TYPE_CHECK, name="evidence_type_valid"),
        CheckConstraint(_VERIFICATION_CHECK, name="verification_status_valid"),
        CheckConstraint(_EXTRACTION_CHECK, name="extraction_method_valid"),
        Index("ix_evidence_record_document", "document_id"),
        Index(
            "ix_evidence_record_document_type",
            "document_id",
            "evidence_type",
        ),
        Index(
            "ix_evidence_record_verification",
            "verification_status",
        ),
        Index("ix_evidence_record_run", "extraction_run_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("document_asset.id", ondelete="CASCADE"),
        nullable=False,
    )
    extraction_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("evidence_extraction_run.id", ondelete="SET NULL"),
        nullable=True,
    )
    evidence_type: Mapped[str] = mapped_column(String(32), nullable=False)
    field_key: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="",
        doc="Stable field identifier within the evidence type.",
    )
    reported_value_json: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="JSON-encoded value as reported in the source.",
    )
    normalized_value_json: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="JSON-encoded value after normalization.",
    )
    units: Mapped[str | None] = mapped_column(String(64), nullable=True)
    raw_source_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    section_title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    table_reference: Mapped[str | None] = mapped_column(String(64), nullable=True)
    figure_reference: Mapped[str | None] = mapped_column(String(64), nullable=True)
    extraction_method: Mapped[str] = mapped_column(
        String(32), nullable=False, default="rule_based", server_default="rule_based"
    )
    verification_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="ai_proposed", server_default="ai_proposed"
    )
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    user_correction_json: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="JSON-encoded record of user corrections to the reported value.",
    )

    def __repr__(self) -> str:
        return (
            f"<EvidenceRecord document_id={self.document_id} "
            f"type={self.evidence_type!r} status={self.verification_status!r}>"
        )