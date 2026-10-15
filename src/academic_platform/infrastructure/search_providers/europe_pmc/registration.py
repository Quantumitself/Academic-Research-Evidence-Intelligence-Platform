"""Registration of the Europe PMC adapter with the default provider registry."""

from __future__ import annotations

import logging

from academic_platform.infrastructure.search_providers.europe_pmc.adapter import (
    build_europe_pmc_adapter,
)
from academic_platform.infrastructure.search_providers.registry import (
    ProviderRegistry,
    default_registry,
)

_logger = logging.getLogger(__name__)


def register_europe_pmc(registry: ProviderRegistry | None = None) -> None:
    """Register the Europe PMC adapter with the given registry."""
    target = registry if registry is not None else default_registry()
    try:
        target.register_factory("europe_pmc", build_europe_pmc_adapter)
    except Exception:  # noqa: BLE001 - boundary
        _logger.exception("Failed to register the Europe PMC adapter")