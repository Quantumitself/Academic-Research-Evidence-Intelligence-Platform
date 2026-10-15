"""AI task routing model.

A task routing entry maps an application task (article summarization,
evidence extraction, and so on) to a provider and model. Routing is the
mechanism by which the application selects a model for a specific
operation without hard-coding the choice.

Design decisions
----------------
- The ``task_key`` is unique across the table. A task has exactly one
  routing entry; the entry is replaced when the user changes the
  routing.
- ``provider_id`` and ``model_id`` are both nullable. When the entry is
  absent, the application falls back to the provider-level and
  model-level defaults declared on those records, and finally to the
  application default provider declared in ``app_settings``.
- The ``fallback_provider_id`` and ``fallback_model_id`` columns allow a
  routing entry to specify a secondary target used when the primary
  fails for a recoverable reason. They are nullable.
- ``parameters_json`` stores per-task generation parameters (temperature,
  top_p, and so on). The application interprets them; the database
  stores them.
"""

from __future__ import annotations

from sqlalchemy import ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from academic_platform.infrastructure.database.base import (
    Base,
    TimestampMixin,
    VersionMixin,
)


class AITaskRouting(Base, TimestampMixin, VersionMixin):
    """Routing configuration for a single application task."""

    __tablename__ = "ai_task_routing"
    __table_args__ = (
        Index("ix_ai_task_routing_task_key", "task_key"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    task_key: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
        doc="Stable task identifier (for example 'article_summarization').",
    )
    provider_id: Mapped[int | None] = mapped_column(
        ForeignKey("ai_provider.id", ondelete="SET NULL"),
        nullable=True,
    )
    model_id: Mapped[int | None] = mapped_column(
        ForeignKey("ai_model.id", ondelete="SET NULL"),
        nullable=True,
    )
    fallback_provider_id: Mapped[int | None] = mapped_column(
        ForeignKey("ai_provider.id", ondelete="SET NULL"),
        nullable=True,
    )
    fallback_model_id: Mapped[int | None] = mapped_column(
        ForeignKey("ai_model.id", ondelete="SET NULL"),
        nullable=True,
    )
    temperature: Mapped[float | None] = mapped_column(nullable=True)
    max_output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    parameters_json: Mapped[str] = mapped_column(
        Text, nullable=False, default="{}", server_default="{}"
    )

    def __repr__(self) -> str:
        return (
            f"<AITaskRouting task={self.task_key!r} "
            f"provider={self.provider_id} model={self.model_id}>"
        )