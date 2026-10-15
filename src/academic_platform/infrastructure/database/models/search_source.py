"""Search source model.

A search source describes a configurable academic search provider. The
model stores the user-visible configuration; credentials are stored
separately in the operating system keyring and are referenced by
identifier.

Design decisions
----------------
- Built-in sources are shipped with the application and their
  configuration is written at first start. They are marked by the
  ``builtin`` flag. Built-in sources cannot be deleted by the user; they
  can be disabled.
- User-defined sources carry their own configuration. Their ``base_url``
  and ``endpoint`` are validated by the application before they are
  persisted; the schema stores the values the application supplied.
- ``parameter_map_json`` stores the provider-specific mapping from
  application query fields to provider query parameters. The
  application interprets this mapping; the database stores it.
- ``rate_limit_json`` and ``capabilities_json`` store provider-specific
  metadata. The application interprets them; the database stores them.
- The unique constraint on ``provider_key`` prevents two configurations
  from sharing the same provider identifier, which would break the
  adapter registry.
"""

from __future__ import annotations

from sqlalchemy import CheckConstraint, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from academic_platform.infrastructure.database.base import (
    Base,
    TimestampMixin,
    VersionMixin,
)

_SOURCE_TYPES = ("builtin", "user_defined")
_TYPE_CHECK = (
    "source_type IN (" + ", ".join(f"'{value}'" for value in _SOURCE_TYPES) + ")"
)

_AUTH_TYPES = ("none", "api_key", "bearer_token")
_AUTH_CHECK = (
    "auth_type IN (" + ", ".join(f"'{value}'" for value in _AUTH_TYPES) + ")"
)


class SearchSource(Base, TimestampMixin, VersionMixin):
    """A configurable academic search source."""

    __tablename__ = "search_source"
    __table_args__ = (
        CheckConstraint(_TYPE_CHECK, name="source_type_valid"),
        CheckConstraint(_AUTH_CHECK, name="auth_type_valid"),
        Index("ix_search_source_enabled", "enabled"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    provider_key: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        unique=True,
        doc="Stable identifier of the provider adapter (for example 'crossref').",
    )
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    base_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    endpoint: Mapped[str] = mapped_column(String(2048), nullable=False, default="")
    http_method: Mapped[str] = mapped_column(
        String(16), nullable=False, default="GET", server_default="GET"
    )
    parameter_map_json: Mapped[str] = mapped_column(
        Text, nullable=False, default="{}", server_default="{}"
    )
    capabilities_json: Mapped[str] = mapped_column(
        Text, nullable=False, default="{}", server_default="{}"
    )
    rate_limit_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    auth_type: Mapped[str] = mapped_column(
        String(32), nullable=False, default="none", server_default="none"
    )
    credential_reference: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
        doc="Opaque reference to a credential stored outside the database.",
    )
    enabled: Mapped[int] = mapped_column(
        nullable=False, default=1, server_default="1"
    )
    timeout_seconds: Mapped[int] = mapped_column(
        Integer, nullable=False, default=20, server_default="20"
    )
    result_limit: Mapped[int] = mapped_column(
        Integer, nullable=False, default=50, server_default="50"
    )
    last_tested_at: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<SearchSource key={self.key!r} type={self.source_type!r}>"