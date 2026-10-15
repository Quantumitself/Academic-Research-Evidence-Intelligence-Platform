"""Tests for the OpenAlex registration helper."""

from __future__ import annotations

from academic_platform.infrastructure.search_providers.openalex.registration import (
    register_openalex,
)
from academic_platform.infrastructure.search_providers.registry import (
    ProviderRegistry,
)


def test_registration_adds_key() -> None:
    registry = ProviderRegistry()
    register_openalex(registry)
    assert "openalex" in registry


def test_registration_is_idempotent() -> None:
    registry = ProviderRegistry()
    register_openalex(registry)
    register_openalex(registry)
    assert registry.registered_keys().count("openalex") == 1


def test_default_registry_contains_openalex_after_import() -> None:
    import academic_platform.infrastructure.search_providers  # noqa: F401

    from academic_platform.infrastructure.search_providers.registry import (
        default_registry,
    )

    registry = default_registry()
    assert "openalex" in registry