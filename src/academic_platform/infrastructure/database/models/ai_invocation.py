"""AI invocation log model.

An AI invocation records a single call to a provider. Invocations are
append-only. The log carries the provider and model used, the prompt
template version, the task, timing information, token counts when the
provider reports them, and the outcome.

Design decisions
----------------
- The log never stores prompt or response bodies. Only identifiers, sizes,
  and metadata are stored so that user content is not duplicated in the
  database beyond what the user's own records already contain.
- ``input_size_bytes`` and ``output_size_bytes`` record the size of the
  request and response bodies. They allow cost estimation and diagnostics
  without storing the bodies themselves.
- ``input_tokens``, ``output_tokens``, and ``total_tokens`` are populated
  when the provider reports them. They are nullable.
- ``status`` is a closed enumeration: ``ok``, ``failed``, ``cancelled``.
- ``error_message`` carries a short summary. Technical diagnostics belong
  in the application logs, not in the database.
- ``request_id`` is the provider's own request identifier, when it
  returns one. It is used to correlate the log with the provider's
  support tooling.
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from academic_platform.infrastructure.database.base import Base, TimestampMixin

_STATUSES = ("ok", "failed", "cancelled")
_STATUS_CHECK = (
    "status IN (" + ", ".join(f"'{value}'" for value in _STATUSES) + ")"
)


class AIInvocation(Base, TimestampMixin):
    """An append-only record of a single AI invocation."""

    __tablename__ = "ai_invocation"
    __table_args__ = (
        CheckConstraint(_STATUS_CHECK, name="status_valid"),
        Index("ix_ai_invocation_started_at", "started_at"),
        Index("ix_ai_invocation_task_started", "task_key", "started_at"),
        Index("ix_ai_invocation_provider_started", "provider_id", "started_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    task_key: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_id: Mapped[int | None] = mapped_column(
        ForeignKey("ai_provider.id", ondelete="SET NULL"),
        nullable=True,
    )
    model_id: Mapped[int | None] = mapped_column(
        ForeignKey("ai_model.id", ondelete="SET NULL"),
        nullable=True,
    )
    provider_key_snapshot: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="",
        doc="Provider key at the time of the invocation, for provenance.",
    )
    model_identifier_snapshot: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        default="",
        doc="Model identifier at the time of the invocation, for provenance.",
    )
    prompt_template_version: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    started_at: Mapped[dt.datetime] = mapped_column(DateTime, nullable=False)
    finished_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    input_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    extra_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return (
            f"<AIInvocation task={self.task_key!r} "
            f"provider={self.provider_key_snapshot!r} status={self.status!r}>"
        )