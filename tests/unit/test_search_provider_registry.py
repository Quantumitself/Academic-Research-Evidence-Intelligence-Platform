"""Tests for the search provider registry."""

from __future__ import annotations

import pytest

from academic_platform.infrastructure.search_providers.adapter import (
    ProviderCapabilities,
    ProviderDescriptor,
    SearchProviderAdapter,
    SearchRequest,
    SearchResponse,
    SourceStatus,
    SourceStatusReport,
)
from academic_platform.infrastructure.search_providers.errors import (
    ProviderConfigurationError,
)
from academic_platform.infrastructure.search_providers.null_adapter import (
    NullSearchProviderAdapter,
)
from academic_platform.infrastructure.search_providers.registry import (
    ProviderRegistry,
    default_registry,
)


class _StubAdapter(SearchProviderAdapter):
    @property
    def descriptor(self) -> ProviderDescriptor:
        return ProviderDescriptor(
            key="stub",
            display_name="Stub",
            base_url="https://stub.invalid",
            documentation_url="https://stub.invalid/docs",
            provider_kind="stub",
            capabilities=ProviderCapabilities(max_results_per_page=10),
        )

    def search(self, request: SearchRequest) -> SearchResponse:
        return SearchResponse(
            provider_key="stub",
            hits=(),
            status=SourceStatusReport(provider_key="stub", status=SourceStatus.OK),
        )

    def test_connection(self) -> SourceStatusReport:
        return SourceStatusReport(provider_key="stub", status=SourceStatus.OK)


def test_register_class_and_get() -> None:
    registry = ProviderRegistry()
    registry.register_class("stub", _StubAdapter)
    adapter = registry.get("stub")
    assert isinstance(adapter, _StubAdapter)


def test_register_factory_and_get() -> None:
    captured: dict = {}

    def factory(config: dict) -> SearchProviderAdapter:
        captured.update(config)
        return _StubAdapter()

    registry = ProviderRegistry()
    registry.register_factory("stub", factory)
    registry.get("stub", config={"a": 1})
    assert captured == {"a": 1}


def test_factory_exception_wrapped() -> None:
    def factory(config: dict) -> SearchProviderAdapter:
        raise RuntimeError("boom")

    registry = ProviderRegistry()
    registry.register_factory("stub", factory)
    with pytest.raises(ProviderConfigurationError):
        registry.get("stub")


def test_register_instance_and_get() -> None:
    adapter = _StubAdapter()
    registry = ProviderRegistry()
    registry.register_instance("stub", adapter)
    assert registry.get("stub") is adapter


def test_unknown_key_raises() -> None:
    registry = ProviderRegistry()
    with pytest.raises(ProviderConfigurationError):
        registry.get("missing")


def test_registered_keys_sorted() -> None:
    registry = ProviderRegistry()
    registry.register_class("b", _StubAdapter)
    registry.register_class("a", _StubAdapter)
    assert registry.registered_keys() == ("a", "b")


def test_unregister() -> None:
    registry = ProviderRegistry()
    registry.register_class("stub", _StubAdapter)
    registry.unregister("stub")
    assert "stub" not in registry


def test_descriptors() -> None:
    registry = ProviderRegistry()
    registry.register_class("stub", _StubAdapter)
    descriptors = registry.descriptors()
    assert len(descriptors) == 1
    assert descriptors[0].key == "stub"


def test_descriptors_reports_construction_failure() -> None:
    def factory(config: dict) -> SearchProviderAdapter:
        raise RuntimeError("boom")

    registry = ProviderRegistry()
    registry.register_factory("broken", factory)
    descriptors = registry.descriptors()
    assert descriptors[0].key == "broken"
    assert "boom" in descriptors[0].notes


def test_register_replaces() -> None:
    registry = ProviderRegistry()
    first = _StubAdapter()
    second = _StubAdapter()
    registry.register_instance("stub", first)
    registry.register_instance("stub", second)
    assert registry.get("stub") is second


def test_default_registry_registers_null() -> None:
    registry = default_registry()
    assert "null" in registry
    adapter = registry.get("null")
    assert isinstance(adapter, NullSearchProviderAdapter)


def test_default_registry_is_singleton() -> None:
    assert default_registry() is default_registry()