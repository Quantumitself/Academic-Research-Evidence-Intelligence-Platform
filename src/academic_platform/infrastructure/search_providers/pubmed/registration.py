"""Registration of the PubMed adapter with the default provider registry.

The registration module is imported by the search providers package's
initializer so that the adapter is available as soon as the package is
imported. Registration is idempotent.
"""

from __future__ import annotations

import logging

from academic_platform.infrastructure.search_providers.pubmed.adapter import (
    build_pubmed_adapter,
)
from academic_platform.infrastructure.search_providers.registry import (
    ProviderRegistry,
    default_registry,
)

_logger = logging.getLogger(__name__)


def register_pubmed(registry: ProviderRegistry | None = None) -> None:
    """Register the PubMed adapter with the given registry."""
    target = registry if registry is not None else default_registry()
    try:
        target.register_factory("pubmed", build_pubmed_adapter)
    except Exception:  # noqa: BLE001 - boundary
        _logger.exception("Failed to register the PubMed adapter")