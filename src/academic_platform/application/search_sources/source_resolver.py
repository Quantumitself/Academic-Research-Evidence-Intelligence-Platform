"""Resolve a persisted source configuration to a provider adapter.

The resolver bridges the application-layer ``SourceConfig`` and the
infrastructure-layer ``SearchProviderAdapter``. It reads the provider
registry, constructs the adapter with the source's configuration, and
caches the result for the lifetime of the resolver.

Design decisions
----------------
- The resolver is constructed per unit of work. Adapters are cached
  within the resolver, not across resolvers, so that configuration
  changes take effect on the next unit of work.
- The resolver never mutates the registry. It reads entries and
  constructs adapters.
- When a provider key is not registered, the resolver returns the null
  adapter from the registry rather than raising. This keeps the search
  page functional even when a source references a provider that the
  application does not yet ship.
"""

from __future__ import annotations

import logging

from academic_platform.application.search_sources.errors import (
    SourceValidationError,
)
from academic_platform.application.search_sources.source_config import SourceConfig
from academic_platform.infrastructure.search_providers.adapter import (
    SearchProviderAdapter,
)
from academic_platform.infrastructure.search_providers.errors import (
    ProviderConfigurationError,
)
from academic_platform.infrastructure.search_providers.registry import (
    ProviderRegistry,
)

_logger = logging.getLogger(__name__)


class SourceResolver:
    """Resolve source configurations to provider adapters."""

    def __init__(self, registry: ProviderRegistry) -> None:
        self._registry = registry
        self._cache: dict[str, SearchProviderAdapter] = {}

    def resolve(self, config: SourceConfig) -> SearchProviderAdapter:
        """Return the adapter for a source configuration.

        Raises
        ------
        SourceValidationError
            If the adapter cannot be constructed and no fallback is
            available. The resolver prefers to fall back to the null
            adapter when the provider is not registered; it raises only
            when the provider is registered but fails to construct with
            the supplied configuration.
        """
        cached = self._cache.get(config.key)
        if cached is not None:
            return cached

        provider_config = self._provider_config(config)
        try:
            adapter = self._registry.get(config.provider_key, config=provider_config)
        except ProviderConfigurationError as exc:
            if config.provider_key not in self._registry:
                _logger.info(
                    "Provider %r is not registered; falling back to the null adapter",
                    config.provider_key,
                )
                adapter = self._registry.get("null")
            else:
                raise SourceValidationError(
                    [f"Unable to construct provider {config.provider_key!r}: {exc}"]
                ) from exc

        self._cache[config.key] = adapter
        return adapter

    def invalidate(self, key: str | None = None) -> None:
        """Drop cached adapters.

        Passing ``None`` clears the entire cache; passing a source key
        drops only that entry. Callers use this after a source's
        configuration changes.
        """
        if key is None:
            self._cache.clear()
        else:
            self._cache.pop(key, None)

    @staticmethod
    def _provider_config(config: SourceConfig) -> dict[str, Any]:
        # The provider adapter receives the source's configuration as a
        # plain dictionary. Adapters interpret the keys they understand
        # and ignore the rest.
        return {
            "base_url": config.base_url,
            "endpoint": config.endpoint,
            "http_method": config.http_method,
            "parameter_map": dict(config.parameter_map),
            "capabilities": dict(config.capabilities),
            "rate_limit": dict(config.rate_limit) if config.rate_limit else None,
            "auth_type": config.auth_type,
            "credential_reference": config.credential_reference,
            "timeout_seconds": config.timeout_seconds,
            "result_limit": config.result_limit,
        }


from typing import Any  # noqa: E402  (needed by the type annotation above)