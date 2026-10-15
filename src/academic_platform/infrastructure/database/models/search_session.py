"""Search session and search result models.

A search session records a single execution of a search. It carries the
query that was executed, the scope, the executed timestamp, and the set
of per-source status reports. Each result returned by the search is
stored as a separate row linked to the session.

Design decisions
----------------
- The session carries the query text as it was executed. Saved queries
  are a separate concept; a session is always tied to a specific
  execution, even when the query is not saved.
- ``source_reports_json`` stores the per-source status as a JSON array.
  The application interprets it; the database stores it. The list is
  bounded by the number of configured sources.
- Each result row links the session to a publication through the
  publication's integer identifier. The result carries the rank and the
  score the provider reported. The application uses these values for
  ordering and for display.
- A unique constraint on ``(session_id, publication_id)`` prevents the
  same publication from appearing twice in one session's result set.
  Deduplication across providers is performed by the search
  orchestration layer before results are persisted; the constraint
  enforces the invariant at the schema level.
- A session has an optional associated saved query. Deleting a saved
  query does not delete its sessions; the sessions carry their own copy
  of the query text.
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from academic_platform.infrastructure.database.base import Base, TimestampMixin

_SCOPES = ("all", "local", "remote")
_SCOPE_CHECK = "scope IN (" + ", ".join(f"'{value}'" for value in _SCOPES) + ")"


class SearchSession(Base, TimestampMixin):
    """A single execution of a search."""

    __tablename__ = "search_session"
    __table_args__ = (
        CheckConstraint(_SCOPE_CHECK, name="scope_valid"),
        Index("ix_search_session_executed_at", "executed_at"),
        Index("ix_search_session_query_key", "query_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    query_id: Mapped[int | None] = mapped_column(
        ForeignKey("saved_search_query.id", ondelete="SET NULL"),
        nullable=True,
    )
    query_text: Mapped[str] = mapped_column(String(2048), nullable=False, default="")
    scope: Mapped[str] = mapped_column(
        String(16), nullable=False, default="all", server_default="all"
    )
    executed_at: Mapped[dt.datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=lambda: dt.datetime.now(dt.timezone.utc).replace(tzinfo=None),
    )
    source_reports_json: Mapped[str] = mapped_column(
        Text, nullable=False, default="[]", server_default="[]"
    )
    partial: Mapped[int] = mapped_column(
        nullable=False, default=0, server_default="0"
    )
    result_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    message: Mapped[str] = mapped_column(Text, nullable=False, default="")

    def __repr__(self) -> str:
        return f"<SearchSession id={self.id} query={self.query_text!r}>"


class SearchResult(Base, TimestampMixin):
    """A single result returned by a search session."""

    __tablename__ = "search_result"
    __table_args__ = (
        UniqueConstraint(
            "session_id",
            "publication_id",
            name="uq_search_result_session_publication",
        ),
        Index("ix_search_result_session_rank", "session_id", "rank"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("search_session.id", ondelete="CASCADE"),
        nullable=False,
    )
    publication_id: Mapped[int] = mapped_column(
        ForeignKey("publication.id", ondelete="CASCADE"),
        nullable=False,
    )
    provider_key: Mapped[str] = mapped_column(String(64), nullable=False)
    rank: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)

    def __repr__(self) -> str:
        return (
            f"<SearchResult session={self.session_id} "
            f"publication={self.publication_id} rank={self.rank}>"
        )