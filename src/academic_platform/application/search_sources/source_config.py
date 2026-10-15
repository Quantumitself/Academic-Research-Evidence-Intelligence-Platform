"""Immutable value objects for search source configuration.

The application layer does not pass ORM rows around. It converts them to
immutable value objects at the boundary so that callers cannot
accidentally mutate persisted state outside a repository transaction.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class SourceConfig:
    """A single search source's persisted configuration."""

    key: str
    provider_key: str
    display_name: str
    source_type: str
    base_url: str
    endpoint: str = ""
    http_method: str = "GET"
    parameter_map: dict[str, Any] = field(default_factory=dict)
    capabilities: dict[str, Any] = field(default_factory=dict)
    rate_limit: dict[str, Any] | None = None
    auth_type: str = "none"
    credential_reference: str | None = None
    enabled: bool = True
    timeout_seconds: int = 20
    result_limit: int = 50
    last_tested_at: str | None = None
    last_error: str | None = None

    @property
    def is_builtin(self) -> bool:
        return self.source_type == "builtin"

    @property
    def requires_credentials(self) -> bool:
        return self.auth_type != "none"


@dataclass(frozen=True, slots=True)
class SourceRecord:
    """A source record paired with its database identifier."""

    id: int
    config: SourceConfig
    created_at: str | None = None
    updated_at: str | None = None
    version: int = 1

    @property
    def key(self) -> str:
        return self.config.key