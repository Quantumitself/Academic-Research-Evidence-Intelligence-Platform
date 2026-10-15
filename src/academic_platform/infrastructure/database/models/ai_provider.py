"""AI provider configuration model.

An AI provider represents a configured source of language-model services.
Providers are either local (a GGUF model served by a local runtime) or
remote (a hosted API). The model stores only the configuration; secrets
live in the operating system keyring and are referenced by identifier.

Design decisions
----------------
- The ``provider_kind`` column distinguishes local GGUF providers from
  OpenAI-compatible APIs and other hosted services. The set is closed;
  new kinds require a migration and an adapter implementation.
- The ``endpoint_url`` is stored for every provider, including local
  providers. Local providers use an HTTP endpoint exposed by the local
  runtime (for example, a ``llama.cpp`` server). The application never
  loads a GGUF file directly; it calls the runtime's HTTP API.
- The ``model_file_path`` column is populated for local providers whose
  runtime accepts a path to a GGUF file. It is nullable for providers
  that identify their model by an API-supplied name.
- The ``enabled`` flag allows a provider to be configured but not used.
  Disabled providers are excluded from task routing.
- The ``default_for_tasks_json`` column stores a JSON array of task
  identifiers for which this provider is the default. Task routing
  consults this column; the database stores it without interpreting it.
- The ``credential_reference`` column stores an opaque identifier for a
  credential in the operating system keyring. It is never a secret value
  itself.
"""

from __future__ import annotations

from sqlalchemy import CheckConstraint, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from academic_platform.infrastructure.database.base import (
    Base,
    TimestampMixin,
    VersionMixin,
)

_PROVIDER_KINDS = (
    "local_gguf",
    "openai_compatible",
    "anthropic",
    "other",
)
_KIND_CHECK = (
    "provider_kind IN ("
    + ", ".join(f"'{value}'" for value in _PROVIDER_KINDS)
    + ")"
)

_AUTH_TYPES = ("none", "api_key", "bearer_token")
_AUTH_CHECK = (
    "auth_type IN (" + ", ".join(f"'{value}'" for value in _AUTH_TYPES) + ")"
)

_HEALTH_STATES = ("unknown", "ok", "failed", "disabled")
_HEALTH_CHECK = (
    "health_state IN ("
    + ", ".join(f"'{value}'" for value in _HEALTH_STATES)
    + ")"
)


class AIProvider(Base, TimestampMixin, VersionMixin):
    """A configured AI provider."""

    __tablename__ = "ai_provider"
    __table_args__ = (
        CheckConstraint(_KIND_CHECK, name="provider_kind_valid"),
        CheckConstraint(_AUTH_CHECK, name="auth_type_valid"),
        CheckConstraint(_HEALTH_CHECK, name="health_state_valid"),
        Index("ix_ai_provider_enabled", "enabled"),
        Index("ix_ai_provider_kind", "provider_kind"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    provider_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    endpoint_url: Mapped[str] = mapped_column(
        String(2048), nullable=False, default=""
    )
    model_file_path: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    auth_type: Mapped[str] = mapped_column(
        String(32), nullable=False, default="none", server_default="none"
    )
    credential_reference: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
        doc="Opaque reference to a credential stored outside the database.",
    )
    context_length: Mapped[int | None] = mapped_column(Integer, nullable=True)
    request_timeout_seconds: Mapped[int] = mapped_column(
        Integer, nullable=False, default=120, server_default="120"
    )
    max_retries: Mapped[int] = mapped_column(
        Integer, nullable=False, default=2, server_default="2"
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
        Text,
        nullable=False,
        default="[]",
        server_default="[]",
        doc="JSON array of task identifiers this provider is default for.",
    )
    runtime_info_json: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="JSON object describing the runtime reported by the provider.",
    )

    def __repr__(self) -> str:
        return (
            f"<AIProvider key={self.key!r} kind={self.provider_kind!r} "
            f"enabled={self.enabled}>"
        )