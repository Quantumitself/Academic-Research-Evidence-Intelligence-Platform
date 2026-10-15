"""Research plan, task, title candidate, methodology proposal, and analysis recommendation models.

A research plan is the structured output of the Research Design
Assistant. It is owned by a research project and is versioned. Tasks are
the actionable items in the plan. Title candidates are proposed titles
that the user may accept. Methodology proposals compare candidate
methodologies with their trade-offs. Analysis recommendations are the
statistical-method suggestions produced by the Statistical Analysis
Advisor.

Design decisions
----------------
- Plans are versioned by insertion: successive saves create new rows.
  The project's most recent plan is retrieved by ordering on
  ``created_at``.
- Title candidates, methodology proposals, and analysis recommendations
  are stored as separate rows so that each can carry its own state
  (accepted, rejected, provisional). The user's decision is a first-class
  attribute.
- The plan carries both structured fields (background, problem,
  objectives) and a JSON payload for fields whose structure varies by
  research tradition. Structured fields are queried; the JSON payload is
  not.
- Tasks are ordered within a plan by the ``position`` column and carry
  their own completion state.
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
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from academic_platform.infrastructure.database.base import (
    Base,
    TimestampMixin,
    VersionMixin,
)

_CANDIDATE_STATES = ("proposed", "accepted", "rejected", "archived")
_CANDIDATE_STATE_CHECK = (
    "state IN (" + ", ".join(f"'{value}'" for value in _CANDIDATE_STATES) + ")"
)


class ResearchPlan(Base, TimestampMixin, VersionMixin):
    """A structured research plan owned by a project."""

    __tablename__ = "research_plan"
    __table_args__ = (
        Index("ix_research_plan_project", "project_id"),
        Index("ix_research_plan_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("research_project.id", ondelete="CASCADE"),
        nullable=False,
    )
    version_label: Mapped[str] = mapped_column(
        String(32), nullable=False, default="1", server_default="1"
    )
    background: Mapped[str] = mapped_column(Text, nullable=False, default="")
    problem_statement: Mapped[str] = mapped_column(Text, nullable=False, default="")
    research_question: Mapped[str] = mapped_column(Text, nullable=False, default="")
    objectives: Mapped[str] = mapped_column(Text, nullable=False, default="")
    design: Mapped[str] = mapped_column(Text, nullable=False, default="")
    population: Mapped[str] = mapped_column(Text, nullable=False, default="")
    sampling: Mapped[str] = mapped_column(Text, nullable=False, default="")
    data_collection: Mapped[str] = mapped_column(Text, nullable=False, default="")
    analysis: Mapped[str] = mapped_column(Text, nullable=False, default="")
    ethics: Mapped[str] = mapped_column(Text, nullable=False, default="")
    limitations: Mapped[str] = mapped_column(Text, nullable=False, default="")
    references_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    open_questions: Mapped[str] = mapped_column(Text, nullable=False, default="")
    extensions_json: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="JSON object for research-tradition-specific fields.",
    )

    def __repr__(self) -> str:
        return f"<ResearchPlan project={self.project_id} version={self.version_label!r}>"


class ResearchTask(Base, TimestampMixin, VersionMixin):
    """An actionable task within a research project."""

    __tablename__ = "research_task"
    __table_args__ = (
        Index("ix_research_task_project_position", "project_id", "position"),
        Index("ix_research_task_completed", "completed"),
        Index("ix_research_task_status", "status"),
        Index("ix_research_task_is_milestone", "is_milestone"),
        CheckConstraint(
            "status IN ('open','in_progress','blocked','done','cancelled')",
            name="status_valid",
        ),
        CheckConstraint(
            "priority IN ('low','normal','high','critical')",
            name="priority_valid",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("research_project.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    position: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    completed: Mapped[int] = mapped_column(
        nullable=False, default=0, server_default="0"
    )
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="open",
        server_default="open",
        doc="Workflow status: open, in_progress, blocked, done, cancelled.",
    )
    priority: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="normal",
        server_default="normal",
        doc="Priority: low, normal, high, critical.",
    )
    is_milestone: Mapped[int] = mapped_column(
        nullable=False,
        default=0,
        server_default="0",
        doc="Set to 1 when the task is a milestone.",
    )
    notes: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
        server_default="",
    )
    completed_at: Mapped[dt.datetime | None] = mapped_column(
        DateTime,
        nullable=True,
    )
    due_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)

    def __repr__(self) -> str:
        return f"<ResearchTask project={self.project_id} title={self.title!r}>"


class ResearchTitleCandidate(Base, TimestampMixin, VersionMixin):
    """A proposed research title."""

    __tablename__ = "research_title_candidate"
    __table_args__ = (
        CheckConstraint(_CANDIDATE_STATE_CHECK, name="state_valid"),
        Index("ix_research_title_candidate_project", "project_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("research_project.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False, default="")
    strengths: Mapped[str] = mapped_column(Text, nullable=False, default="")
    problems: Mapped[str] = mapped_column(Text, nullable=False, default="")
    assumptions: Mapped[str] = mapped_column(Text, nullable=False, default="")
    state: Mapped[str] = mapped_column(
        String(16), nullable=False, default="proposed", server_default="proposed"
    )

    def __repr__(self) -> str:
        return (
            f"<ResearchTitleCandidate project={self.project_id} "
            f"state={self.state!r} title={self.title!r}>"
        )


class MethodologyProposal(Base, TimestampMixin, VersionMixin):
    """A methodology proposal with its trade-offs."""

    __tablename__ = "methodology_proposal"
    __table_args__ = (
        CheckConstraint(_CANDIDATE_STATE_CHECK, name="state_valid"),
        Index("ix_methodology_proposal_project", "project_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("research_project.id", ondelete="CASCADE"),
        nullable=False,
    )
    methodology_key: Mapped[str] = mapped_column(String(64), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    rationale: Mapped[str] = mapped_column(Text, nullable=False, default="")
    strengths: Mapped[str] = mapped_column(Text, nullable=False, default="")
    limitations: Mapped[str] = mapped_column(Text, nullable=False, default="")
    assumptions: Mapped[str] = mapped_column(Text, nullable=False, default="")
    data_requirements: Mapped[str] = mapped_column(Text, nullable=False, default="")
    ethical_notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    state: Mapped[str] = mapped_column(
        String(16), nullable=False, default="proposed", server_default="proposed"
    )

    def __repr__(self) -> str:
        return (
            f"<MethodologyProposal project={self.project_id} "
            f"key={self.methodology_key!r} state={self.state!r}>"
        )


class AnalysisRecommendation(Base, TimestampMixin, VersionMixin):
    """A statistical-analysis recommendation."""

    __tablename__ = "analysis_recommendation"
    __table_args__ = (
        CheckConstraint(_CANDIDATE_STATE_CHECK, name="state_valid"),
        Index("ix_analysis_recommendation_project", "project_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("research_project.id", ondelete="CASCADE"),
        nullable=False,
    )
    method_key: Mapped[str] = mapped_column(String(64), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    rationale: Mapped[str] = mapped_column(Text, nullable=False, default="")
    assumptions: Mapped[str] = mapped_column(Text, nullable=False, default="")
    diagnostics: Mapped[str] = mapped_column(Text, nullable=False, default="")
    alternatives: Mapped[str] = mapped_column(Text, nullable=False, default="")
    cautions: Mapped[str] = mapped_column(Text, nullable=False, default="")
    state: Mapped[str] = mapped_column(
        String(16), nullable=False, default="proposed", server_default="proposed"
    )

    def __repr__(self) -> str:
        return (
            f"<AnalysisRecommendation project={self.project_id} "
            f"key={self.method_key!r} state={self.state!r}>"
        )