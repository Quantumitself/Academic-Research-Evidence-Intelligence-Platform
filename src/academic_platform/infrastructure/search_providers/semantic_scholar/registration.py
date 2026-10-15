"""Registration of the Semantic Scholar adapter with the default provider registry.

The registration module is imported by the search providers package's
initializer so that the adapter is available as soon as the package is
imported. Registration is idempotent: importing the module multiple times
registers the adapter once.

Design decisions
----------------
- The adapter is registered through the registry's factory API so that
  the adapter is constructed with the source's configuration.
- Registration never raises. A failure is logged and the adapter is not
  registered; the null adapter remains available as a fallback.
"""

from __future__ import annotations

import logging

from academic_platform.infrastructure.search_providers.registry import (
    ProviderRegistry,
    default_registry,
)
from academic_platform.infrastructure.search_providers.semantic_scholar.adapter import (
    build_semantic_scholar_adapter,
)

_logger = logging.getLogger(__name__)


def register_semantic_scholar(registry: ProviderRegistry | None = None) -> None:
    """Register the Semantic Scholar adapter with the given registry.

    When ``registry`` is None the default registry is used.
    """
    target = registry if registry is not None else default_registry()
    try:
        target.register_factory(
            "semantic_scholar", build_semantic_scholar_adapter
        )
    except Exception:  # noqa: BLE001 - boundary
        _logger.exception("Failed to register the Semantic Scholar adapter")