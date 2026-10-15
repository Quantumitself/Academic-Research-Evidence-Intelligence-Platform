"""Research question model.

A research question belongs to a research project. A project may have
zero or more questions; the primary question is identified by the
``is_primary`` flag. The schema does not enforce a unique primary question
because the application's workflow allows the user to designate a
primary question explicitly and to change that designation over time;
enforcing it in the schema would create spurious write failures during
that workflow.

Design decisions
----------------
- Questions are ordered within a project through the ``position`` column.
  The application controls the ordering; the schema only stores it.
- ``kind`` distinguishes different question types (main, sub, exploratory,
  hypothesis). The set is closed and enforced by a check constraint.
"""

from __future__ import annotations

from sqlalchemy import CheckConstraint, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from academic_platform.infrastructure.database.base import (
    Base,
    TimestampMixin,
    VersionMixin,
)

_QUESTION_KINDS = (
    "main",
    "sub",
    "exploratory",
    "hypothesis",
)

_KIND_CHECK = "kind IN (" + ", ".join(f"'{value}'" for value in _QUESTION_KINDS) + ")"


class ResearchQuestion(Base, TimestampMixin, VersionMixin):
    """A research question belonging to a project."""

    __tablename__ = "research_question"
    __table_args__ = (
        CheckConstraint(_KIND_CHECK, name="kind_valid"),
        Index("ix_research_question_project_position", "project_id", "position"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("research_project.id", ondelete="CASCADE"),
        nullable=False,
    )
    text: Mapped[str] = mapped_column(String(2048), nullable=False, default="")
    kind: Mapped[str] = mapped_column(
        String(32), nullable=False, default="main", server_default="main"
    )
    is_primary: Mapped[int] = mapped_column(
        nullable=False, default=0, server_default="0"
    )
    position: Mapped[int] = mapped_column(nullable=False, default=0, server_default="0")

    def __repr__(self) -> str:
        return f"<ResearchQuestion project={self.project_id} kind={self.kind!r}>"