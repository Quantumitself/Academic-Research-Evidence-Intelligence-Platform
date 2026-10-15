"""Search provider adapters.

This subpackage owns everything related to academic search providers:

- The adapter interface every provider implements.
- The value objects describing provider capabilities and search requests
  and responses.
- The provider registry that maps a provider key to its adapter class.
- The concrete adapters for each supported provider.

The subpackage never imports Qt. It may import from ``httpx`` for
networking and from ``pydantic`` for boundary schemas. The presentation
layer never imports from this subpackage directly; the application layer
is the boundary.
"""

from __future__ import annotations

import logging

from academic_platform.infrastructure.search_providers.adapter import (
    ProviderCapabilities,
    ProviderDescriptor,
    ProviderFilterSupport,
    SearchHit,
    SearchProviderAdapter,
    SearchRequest,
    SearchResponse,
    SourceStatus,
    SourceStatusReport,
)
from academic_platform.infrastructure.search_providers.errors import (
    ProviderConfigurationError,
    ProviderError,
    ProviderRequestError,
    ProviderResponseError,
    ProviderUnavailableError,
)
from academic_platform.infrastructure.search_providers.null_adapter import (
    NullSearchProviderAdapter,
)
from academic_platform.infrastructure.search_providers.registry import (
    ProviderRegistry,
    default_registry,
)

__all__ = [
    "NullSearchProviderAdapter",
    "ProviderCapabilities",
    "ProviderConfigurationError",
    "ProviderDescriptor",
    "ProviderError",
    "ProviderFilterSupport",
    "ProviderRegistry",
    "ProviderRequestError",
    "ProviderResponseError",
    "ProviderUnavailableError",
    "SearchHit",
    "SearchProviderAdapter",
    "SearchRequest",
    "SearchResponse",
    "SourceStatus",
    "SourceStatusReport",
    "default_registry",
]

_logger = logging.getLogger(__name__)


def _register_concrete_providers() -> None:
    """Register every concrete provider with the default registry.

    Importing a registration module registers the provider as a side
    effect. Each registration function is also called explicitly so the
    adapter is present even when the module was already imported earlier
    in the process. Failures are logged and tolerated; the null adapter
    remains available as a fallback.
    """
    try:
        from academic_platform.infrastructure.search_providers.crossref import (
            registration as crossref_registration,
        )
    except Exception:  # noqa: BLE001 - boundary
        _logger.exception("Failed to import the Crossref registration module")
    else:
        try:
            crossref_registration.register_crossref()
        except Exception:  # noqa: BLE001 - boundary
            _logger.exception("Failed to register the Crossref adapter")

    try:
        from academic_platform.infrastructure.search_providers.openalex import (
            registration as openalex_registration,
        )
    except Exception:  # noqa: BLE001 - boundary
        _logger.exception("Failed to import the OpenAlex registration module")
    else:
        try:
            openalex_registration.register_openalex()
        except Exception:  # noqa: BLE001 - boundary
            _logger.exception("Failed to register the OpenAlex adapter")

    try:
        from academic_platform.infrastructure.search_providers.semantic_scholar import (
            registration as semantic_scholar_registration,
        )
    except Exception:  # noqa: BLE001 - boundary
        _logger.exception(
            "Failed to import the Semantic Scholar registration module"
        )
    else:
        try:
            semantic_scholar_registration.register_semantic_scholar()
        except Exception:  # noqa: BLE001 - boundary
            _logger.exception("Failed to register the Semantic Scholar adapter")

    try:
        from academic_platform.infrastructure.search_providers.pubmed import (
            registration as pubmed_registration,
        )
    except Exception:  # noqa: BLE001 - boundary
        _logger.exception("Failed to import the PubMed registration module")
    else:
        try:
            pubmed_registration.register_pubmed()
        except Exception:  # noqa: BLE001 - boundary
            _logger.exception("Failed to register the PubMed adapter")

    try:
        from academic_platform.infrastructure.search_providers.europe_pmc import (
            registration as europe_pmc_registration,
        )
    except Exception:  # noqa: BLE001 - boundary
        _logger.exception(
            "Failed to import the Europe PMC registration module"
        )
    else:
        try:
            europe_pmc_registration.register_europe_pmc()
        except Exception:  # noqa: BLE001 - boundary
            _logger.exception("Failed to register the Europe PMC adapter")

    try:
        from academic_platform.infrastructure.search_providers.arxiv import (
            registration as arxiv_registration,
        )
    except Exception:  # noqa: BLE001 - boundary
        _logger.exception("Failed to import the arXiv registration module")
    else:
        try:
            arxiv_registration.register_arxiv()
        except Exception:  # noqa: BLE001 - boundary
            _logger.exception("Failed to register the arXiv adapter")


_register_concrete_providers()