"""Registration of the arXiv adapter with the default provider registry."""

from __future__ import annotations

import logging

from academic_platform.infrastructure.search_providers.arxiv.adapter import (
    build_arxiv_adapter,
)
from academic_platform.infrastructure.search_providers.registry import (
    ProviderRegistry,
    default_registry,
)

_logger = logging.getLogger(__name__)


def register_arxiv(registry: ProviderRegistry | None = None) -> None:
    """Register the arXiv adapter with the given registry."""
    target = registry if registry is not None else default_registry()
    try:
        target.register_factory("arxiv", build_arxiv_adapter)
    except Exception:  # noqa: BLE001 - boundary
        _logger.exception("Failed to register the arXiv adapter")