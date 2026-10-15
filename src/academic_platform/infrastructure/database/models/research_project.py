"""Research project model.

A research project represents a study under development. It owns a
lifecycle stage, a working title, a topic, and a set of research
questions. Collections, documents, and evidence link to a project through
their own foreign keys.

Design decisions
----------------
- The project's ``key`` is a stable, human-readable identifier. It is
  immutable after creation and is used in audit events and in the external
  API in place of the integer primary key.
- ``stage`` is stored as a short string with a check constraint. The set
  of stages is closed; new stages require a migration and a schema update.
- ``project_metadata`` is stored as a JSON-encoded text column. The
  application does not query inside it, so no JSON indexing is required.
  Fields that need to be queried (title, topic, stage) are declared as
  dedicated columns.
- The ``version`` column supports optimistic concurrency. Projects are
  long-lived and edited frequently; detecting a concurrent edit prevents
  a UI save from silently overwriting another window's change.
"""

from __future__ import annotations

from sqlalchemy import CheckConstraint, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from academic_platform.infrastructure.database.base import (
    Base,
    TimestampMixin,
    VersionMixin,
)

_PROJECT_STAGES = (
    "idea",
    "design",
    "collection",
    "analysis",
    "writing",
    "complete",
    "archived",
)

_STAGE_CHECK = "stage IN (" + ", ".join(f"'{value}'" for value in _PROJECT_STAGES) + ")"


class ResearchProject(Base, TimestampMixin, VersionMixin):
    """A research project under development."""

    __tablename__ = "research_project"
    __table_args__ = (
        CheckConstraint(_STAGE_CHECK, name="stage_valid"),
        Index("ix_research_project_stage", "stage"),
        Index("ix_research_project_updated_at", "updated_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    topic: Mapped[str] = mapped_column(String(1024), nullable=False, default="")
    stage: Mapped[str] = mapped_column(
        String(32), nullable=False, default="idea", server_default="idea"
    )
    project_metadata: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Optional JSON-encoded project metadata.",
    )

    def __repr__(self) -> str:
        return f"<ResearchProject key={self.key!r} stage={self.stage!r}>"