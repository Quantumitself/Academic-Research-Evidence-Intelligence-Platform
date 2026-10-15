"""AI model configuration model.

An AI model belongs to an AI provider. A provider may expose zero or more
models; the set is populated by the provider's model-discovery endpoint
when available, or by manual entry when the provider does not support
discovery.

Design decisions
----------------
- The ``model_identifier`` is the identifier the provider uses to address
  the model. It is unique within a provider, enforced by a composite
  unique constraint.
- ``capabilities_json`` stores provider-declared capabilities (streaming,
  structured output, tool use, vision). The application reads this to
  decide whether a task can be routed to the model; the database stores
  it without interpreting it.
- ``context_length`` and ``max_output_tokens`` are optional overrides
  that supersede whatever the provider reports. They are null when the
  application uses the provider-reported value.
- The ``enabled`` flag allows a model to be listed but not routed to.
- ``default_for_tasks_json`` mirrors the provider's column but at the
  model level. Task routing consults the model-level list first, then the
  provider-level list.
"""

from __future__ import annotations

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from academic_platform.infrastructure.database.base import (
    Base,
    TimestampMixin,
    VersionMixin,
)

_HEALTH_STATES = ("unknown", "ok", "failed", "disabled")
_HEALTH_CHECK = (
    "health_state IN ("
    + ", ".join(f"'{value}'" for value in _HEALTH_STATES)
    + ")"
)


class AIModel(Base, TimestampMixin, VersionMixin):
    """A model exposed by an AI provider."""

    __tablename__ = "ai_model"
    __table_args__ = (
        UniqueConstraint(
            "provider_id",
            "model_identifier",
            name="uq_ai_model_provider_identifier",
        ),
        CheckConstraint(_HEALTH_CHECK, name="health_state_valid"),
        Index("ix_ai_model_provider_enabled", "provider_id", "enabled"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    provider_id: Mapped[int] = mapped_column(
        ForeignKey("ai_provider.id", ondelete="CASCADE"),
        nullable=False,
    )
    model_identifier: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    context_length: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    capabilities_json: Mapped[str] = mapped_column(
        Text, nullable=False, default="{}", server_default="{}"
    )
    enabled: Mapped[int] = mapped_column(
        nullable=False, default=1, server_default="1"
    )
    health_state: Mapped[str] = mapped_column(
        String(16), nullable=False, default="unknown", server_default="unknown"
    )
    last_tested_at: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    default_for_tasks_json: Mapped[str] = mapped_column(
        Text, nullable=False, default="[]", server_default="[]"
    )

    def __repr__(self) -> str:
        return (
            f"<AIModel provider_id={self.provider_id} "
            f"identifier={self.model_identifier!r}>"
        )