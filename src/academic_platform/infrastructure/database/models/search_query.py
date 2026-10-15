"""Saved search query model.

A saved search query is a reusable search definition. It carries the
search term, the scope (all, local, remote), the filter payload, the
target source set, and an optional user-supplied name.

Design decisions
----------------
- The ``filter_json`` column stores the filter state as produced by the
  search UI. The application interprets it; the database stores it.
- ``source_ids_json`` stores the identifiers of the search sources the
  query targets. The application resolves the identifiers to sources
  when the query is executed.
- ``last_executed_at`` is updated whenever the query is executed. The
  application sets this value explicitly; the schema stores it.
"""

from __future__ import annotations

from sqlalchemy import CheckConstraint, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from academic_platform.infrastructure.database.base import (
    Base,
    TimestampMixin,
    VersionMixin,
)

_SCOPES = ("all", "local", "remote")
_SCOPE_CHECK = "scope IN (" + ", ".join(f"'{value}'" for value in _SCOPES) + ")"


class SavedSearchQuery(Base, TimestampMixin, VersionMixin):
    """A saved, reusable search definition."""

    __tablename__ = "saved_search_query"
    __table_args__ = (
        CheckConstraint(_SCOPE_CHECK, name="scope_valid"),
        Index("ix_saved_search_query_scope", "scope"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    query_text: Mapped[str] = mapped_column(String(2048), nullable=False, default="")
    scope: Mapped[str] = mapped_column(
        String(16), nullable=False, default="all", server_default="all"
    )
    filter_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_ids_json: Mapped[str] = mapped_column(
        Text, nullable=False, default="[]", server_default="[]"
    )
    last_executed_at: Mapped[str | None] = mapped_column(String(64), nullable=True)

    def __repr__(self) -> str:
        return f"<SavedSearchQuery key={self.key!r} scope={self.scope!r}>"