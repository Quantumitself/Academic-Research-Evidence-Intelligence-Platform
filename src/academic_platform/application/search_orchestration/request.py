"""Immutable value objects describing a search orchestration request.

The orchestration request combines the provider-neutral ``SearchRequest``
with the set of sources to target and the concurrency policy. It is
constructed by the presentation layer or by the external API boundary
and is passed unchanged to the orchestrator.

Design decisions
----------------
- The source selection is a set of source keys. The orchestrator
  resolves the keys to source records through the source registry
  service. This keeps the request decoupled from the source registry's
  internal identifiers.
- ``all_enabled`` selects every source that the source registry reports
  as enabled. When ``all_enabled`` is True, the explicit ``source_keys``
  is ignored; this makes the caller's intent unambiguous.
- The concurrency policy is bounded. A value below 1 or above the
  application's maximum is rejected at construction.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from academic_platform.infrastructure.search_providers.adapter import (
    SearchRequest,
)

_MAX_CONCURRENCY = 16


@dataclass(frozen=True, slots=True)
class SourceSelection:
    """Describes which sources a search targets.

    Attributes
    ----------
    all_enabled:
        When True, every enabled source is targeted. The explicit
        ``source_keys`` is ignored.
    source_keys:
        The source keys to target when ``all_enabled`` is False.
    """

    all_enabled: bool = True
    source_keys: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.all_enabled and not self.source_keys:
            raise ValueError(
                "source_keys must not be empty when all_enabled is False"
            )


@dataclass(frozen=True, slots=True)
class SearchOrchestrationRequest:
    """A search request across one or more sources.

    Attributes
    ----------
    search_request:
        The provider-neutral search request executed against each
        selected source.
    selection:
        The set of sources to target.
    max_concurrency:
        Maximum number of adapters executed in parallel. Bounded to
        ``_MAX_CONCURRENCY``.
    record_session:
        When True, the orchestrator records a ``SearchSession`` row and
        one ``SearchResult`` row per returned hit, and persists the
        canonical publications.
    session_scope:
        A short label describing the caller's scope (``"local"``,
        ``"remote"``, or a free-form string). Recorded on the session.
    """

    search_request: SearchRequest
    selection: SourceSelection = field(default_factory=SourceSelection)
    max_concurrency: int = 4
    record_session: bool = True
    session_scope: str = "remote"

    def __post_init__(self) -> None:
        if self.max_concurrency < 1 or self.max_concurrency > _MAX_CONCURRENCY:
            raise ValueError(
                f"max_concurrency must be between 1 and {_MAX_CONCURRENCY}"
            )
        if self.search_request.is_empty:
            raise ValueError("search_request must not be empty")
        if not isinstance(self.selection, SourceSelection):
            raise ValueError("selection must be a SourceSelection")
        if self.session_scope not in {"local", "remote", "all"}:
            raise ValueError("session_scope must be one of: local, remote, all")