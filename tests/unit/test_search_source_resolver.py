"""Tests for the source resolver."""

from __future__ import annotations

import pytest

from academic_platform.application.search_sources.errors import (
    SourceValidationError,
)
from academic_platform.application.search_sources.source_config import (
    SourceConfig,
)
from academic_platform.application.search_sources.source_resolver import (
    SourceResolver,
)
from academic_platform.infrastructure.search_providers.adapter import (
    ProviderCapabilities,
    ProviderDescriptor,
    SearchProviderAdapter,
    SearchRequest,
    SearchResponse,
    SourceStatus,
    SourceStatusReport,
)
from academic_platform.infrastructure.search_providers.null_adapter import (
    NullSearchProviderAdapter,
)
from academic_platform.infrastructure.search_providers.registry import (
    ProviderRegistry,
)


class _StubAdapter(SearchProviderAdapter):
    def __init__(self, key: str = "stub") -> None:
        self._key = key

    @property
    def descriptor(self) -> ProviderDescriptor:
        return ProviderDescriptor(
            key=self._key,
            display_name="Stub",
            base_url="https://stub.invalid",
            documentation_url="https://stub.invalid/docs",
            provider_kind=self._key,
            capabilities=ProviderCapabilities(max_results_per_page=10),
        )

    def search(self, request: SearchRequest) -> SearchResponse:
        return SearchResponse(
            provider_key=self._key,
            status=SourceStatusReport(
                provider_key=self._key, status=SourceStatus.OK
            ),
        )

    def test_connection(self) -> SourceStatusReport:
        return SourceStatusReport(provider_key=self._key, status=SourceStatus.OK)


def _config(**overrides) -> SourceConfig:
    defaults = {
        "key": "example",
        "provider_key": "stub",
        "display_name": "Example",
        "source_type": "user_defined",
        "base_url": "https://stub.invalid",
    }
    defaults.update(overrides)
    return SourceConfig(**defaults)


def test_resolves_registered_provider() -> None:
    registry = ProviderRegistry()
    registry.register_class("stub", _StubAdapter)
    resolver = SourceResolver(registry)
    adapter = resolver.resolve(_config())
    assert isinstance(adapter, _StubAdapter)


def test_falls_back_to_null_adapter_for_unregistered_provider() -> None:
    registry = ProviderRegistry()
    registry.register_instance("null", NullSearchProviderAdapter())
    resolver = SourceResolver(registry)
    adapter = resolver.resolve(_config(provider_key="not-registered"))
    assert isinstance(adapter, NullSearchProviderAdapter)


def test_caches_by_source_key() -> None:
    registry = ProviderRegistry()
    registry.register_class("stub", _StubAdapter)
    resolver = SourceResolver(registry)
    first = resolver.resolve(_config())
    second = resolver.resolve(_config())
    assert first is second


def test_invalidate_specific_key() -> None:
    registry = ProviderRegistry()
    registry.register_class("stub", _StubAdapter)
    resolver = SourceResolver(registry)
    first = resolver.resolve(_config())
    resolver.invalidate("example")
    second = resolver.resolve(_config())
    assert first is not second


def test_invalidate_all() -> None:
    registry = ProviderRegistry()
    registry.register_class("stub", _StubAdapter)
    resolver = SourceResolver(registry)
    first = resolver.resolve(_config())
    resolver.invalidate()
    second = resolver.resolve(_config())
    assert first is not second


def test_registered_but_failing_factory_raises() -> None:
    def factory(config):
        raise RuntimeError("boom")

    registry = ProviderRegistry()
    registry.register_factory("broken", factory)
    resolver = SourceResolver(registry)
    with pytest.raises(SourceValidationError):
        resolver.resolve(_config(provider_key="broken"))