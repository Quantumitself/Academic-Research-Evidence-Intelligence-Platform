"""Search provider adapter interface and value objects.

Every provider implements ``SearchProviderAdapter``. The interface is
narrow on purpose:

- ``descriptor`` describes the provider: its key, display name, base URL,
  authentication requirements, and capabilities.
- ``search`` executes a single search against the provider and returns a
  ``SearchResponse``.
- ``test_connection`` verifies that the provider is reachable and that
  the credentials, if any, are accepted. It returns a status report
  rather than raising for transient failures.

Design decisions
----------------
- The interface is synchronous. Long-running work is the caller's
  responsibility; the orchestration layer executes adapters on a worker
  thread. Synchronous adapters are simpler to test and easier to reason
  about than asynchronous ones.
- Value objects are immutable dataclasses. Adapters return fresh
  instances on every call; they never mutate the request.
- ``SearchRequest`` carries only the parameters the application
  understands. Provider-specific parameters are expressed through the
  ``extra`` mapping, which adapters interpret using the provider's
  configuration.
- ``SearchHit`` is provider-neutral. It carries the normalized fields
  the application uses across providers plus the provider-specific
  identifier and URL.
- ``SearchResponse`` carries the hits, the number of hits returned, the
  total reported by the provider (when available), the cursor for
  pagination (when available), and the per-request status report.
- ``SourceStatusReport`` describes the outcome of a single request.
  The orchestration layer aggregates per-source reports across providers
  when a search is executed against more than one source.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class SourceStatus(str, Enum):
    """Outcome of a single request against a provider."""

    OK = "ok"
    FAILED = "failed"
    SKIPPED = "skipped"
    DISABLED = "disabled"


@dataclass(frozen=True, slots=True)
class ProviderFilterSupport:
    """Describes which filters a provider natively supports.

    Each field is True when the provider accepts the corresponding filter
    as a first-class parameter. The orchestration layer uses this to
    decide whether a filter can be pushed down to the provider or must be
    applied locally to the returned results.
    """

    year_range: bool = False
    author: bool = False
    venue: bool = False
    doi: bool = False
    open_access: bool = False
    language: bool = False
    study_type: bool = False
    sort_by_date: bool = False
    sort_by_relevance: bool = True


@dataclass(frozen=True, slots=True)
class ProviderCapabilities:
    """Describes what a provider can do beyond plain keyword search.

    The orchestration layer reads these flags to decide which optional
    features are available for a given provider. A provider that does not
    support pagination returns only the first page; a provider that does
    not support abstracts returns hits without abstract text.
    """

    pagination: bool = False
    cursor_pagination: bool = False
    abstract_in_results: bool = True
    citation_counts: bool = False
    open_access_flag: bool = False
    requires_api_key: bool = False
    supports_multiple_identifiers: bool = False
    max_results_per_page: int = 100


@dataclass(frozen=True, slots=True)
class ProviderDescriptor:
    """Static description of a provider.

    The descriptor is returned by ``SearchProviderAdapter.descriptor`` and
    is used by the registry, the source-management UI, and diagnostics.
    """

    key: str
    display_name: str
    base_url: str
    documentation_url: str
    provider_kind: str
    filters: ProviderFilterSupport = field(default_factory=ProviderFilterSupport)
    capabilities: ProviderCapabilities = field(default_factory=ProviderCapabilities)
    notes: str = ""


@dataclass(frozen=True, slots=True)
class SearchRequest:
    """A provider-neutral search request.

    Attributes
    ----------
    query:
        The free-text query. Empty strings are permitted only when the
        request also carries a DOI or another identifier in ``extra``;
        adapters reject identifier-only requests that omit the identifier.
    limit:
        Maximum number of hits to return. Adapters clamp this to the
        provider's ``max_results_per_page``.
    offset:
        Zero-based index of the first hit to return. Adapters that do not
        support offset pagination ignore this value.
    cursor:
        Opaque pagination cursor returned by a previous call. Only
        meaningful when the provider's capabilities include
        ``cursor_pagination``.
    year_from, year_to:
        Optional inclusive year range. Adapters that do not support year
        filtering ignore these values.
    author:
        Optional author filter.
    venue:
        Optional venue filter.
    doi:
        Optional DOI. When supplied, adapters that support DOI lookup
        return the single matching work.
    open_access_only:
        When True, adapters that support the open-access filter return
        only open-access works.
    language:
        Optional language filter.
    sort:
        Sort mode: ``relevance`` or ``date_desc`` or ``date_asc``.
    extra:
        Provider-specific parameters. Adapters interpret keys they
        understand and ignore the rest.
    """

    query: str = ""
    limit: int = 50
    offset: int = 0
    cursor: str | None = None
    year_from: int | None = None
    year_to: int | None = None
    author: str | None = None
    venue: str | None = None
    doi: str | None = None
    open_access_only: bool = False
    language: str | None = None
    sort: str = "relevance"
    extra: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.limit <= 0:
            raise ValueError("limit must be positive")
        if self.offset < 0:
            raise ValueError("offset must be non-negative")
        if self.year_from is not None and self.year_from < 0:
            raise ValueError("year_from must be non-negative")
        if (
            self.year_from is not None
            and self.year_to is not None
            and self.year_from > self.year_to
        ):
            raise ValueError("year_from must not exceed year_to")
        if self.sort not in {"relevance", "date_desc", "date_asc"}:
            raise ValueError(
                "sort must be one of: relevance, date_desc, date_asc"
            )

    @property
    def has_identifier(self) -> bool:
        """Return True when the request carries a DOI or another identifier."""
        return bool(self.doi) or "identifier" in self.extra

    @property
    def is_empty(self) -> bool:
        """Return True when the request has no query and no identifier."""
        return not self.query.strip() and not self.has_identifier


@dataclass(frozen=True, slots=True)
class SearchHit:
    """A single provider-neutral search hit.

    The ``provider_key`` and ``provider_identifier`` fields together form
    the provider's stable identifier for the work. The application uses
    the pair to correlate hits across runs and to build the publication's
    stable key.
    """

    provider_key: str
    provider_identifier: str
    title: str = ""
    abstract: str = ""
    authors: tuple[str, ...] = ()
    year: int | None = None
    venue: str = ""
    doi: str | None = None
    language: str | None = None
    is_open_access: bool = False
    citation_count: int | None = None
    url: str | None = None
    score: float | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class SourceStatusReport:
    """Outcome of a single request against a provider."""

    provider_key: str
    status: SourceStatus
    result_count: int = 0
    message: str = ""
    duration_ms: int | None = None


@dataclass(frozen=True, slots=True)
class SearchResponse:
    """Result of executing a search request against a provider."""

    provider_key: str
    hits: tuple[SearchHit, ...] = ()
    total: int | None = None
    next_cursor: str | None = None
    status: SourceStatusReport | None = None


class SearchProviderAdapter(ABC):
    """Abstract base class for search provider adapters.

    Concrete adapters implement ``descriptor``, ``search``, and
    ``test_connection``. They may override ``capabilities`` and
    ``filter_support`` convenience accessors, but the descriptor is the
    authoritative source.
    """

    @property
    @abstractmethod
    def descriptor(self) -> ProviderDescriptor:
        """Return the static descriptor of this provider."""

    @abstractmethod
    def search(self, request: SearchRequest) -> SearchResponse:
        """Execute a search request against the provider.

        Implementations must raise ``ProviderError`` subclasses on
        failure. They must not raise any other exception type; adapters
        translate transport and parsing failures at their boundary.
        """

    @abstractmethod
    def test_connection(self) -> SourceStatusReport:
        """Verify that the provider is reachable.

        The method returns a report rather than raising for transient
        failures. It raises ``ProviderConfigurationError`` only when the
        provider is misconfigured (for example, a missing credential
        that the adapter requires).
        """

    # ------------------------------------------------------------------
    # Convenience accessors
    # ------------------------------------------------------------------
    @property
    def provider_key(self) -> str:
        """Return the provider's stable key."""
        return self.descriptor.key

    @property
    def capabilities(self) -> ProviderCapabilities:
        """Return the provider's capabilities."""
        return self.descriptor.capabilities

    @property
    def filter_support(self) -> ProviderFilterSupport:
        """Return the provider's filter support."""
        return self.descriptor.filters