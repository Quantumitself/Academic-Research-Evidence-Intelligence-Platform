"""Audit event model.

An audit event records a notable action performed by the application or
by the user. Events are append-only: they are never updated or deleted by
application code. The table is used for diagnostics, for the activity
timeline on the dashboard, and for support investigations.

Design decisions
----------------
- The table stores the actor (a user key or the literal ``"system"``), the
  action identifier, the target type and identifier, and a small JSON
  payload. The payload is intentionally unstructured; it carries
  context-specific detail that varies by action.
- Events are timestamped in UTC. ``created_at`` from ``TimestampMixin``
  serves as the event time. A separate ``occurred_at`` column is provided
  for events that are recorded after the fact with a distinct time.
- The table is indexed on ``occurred_at`` for the timeline query and on
  ``(actor, occurred_at)`` for per-user timelines.
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import DateTime, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from academic_platform.infrastructure.database.base import Base, TimestampMixin


class AuditEvent(Base, TimestampMixin):
    """An append-only audit record."""

    __tablename__ = "audit_event"
    __table_args__ = (
        Index("ix_audit_event_occurred_at", "occurred_at"),
        Index("ix_audit_event_actor_occurred_at", "actor", "occurred_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    actor: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="system",
        doc="User key of the actor, or 'system' for application-initiated events.",
    )
    action: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        doc="Stable action identifier (for example 'project.created').",
    )
    target_type: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        doc="Logical type of the target (for example 'research_project').",
    )
    target_identifier: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        doc="Identifier of the target within its type.",
    )
    summary: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
        default="",
        doc="Short human-readable summary.",
    )
    payload_json: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Optional JSON-encoded payload with action-specific detail.",
    )
    occurred_at: Mapped[dt.datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=lambda: dt.datetime.now(dt.timezone.utc).replace(tzinfo=None),
        doc="UTC timestamp when the event occurred.",
    )

    def __repr__(self) -> str:
        return f"<AuditEvent action={self.action!r} actor={self.actor!r}>"