"""Tests for the Semantic Scholar registration helper."""

from __future__ import annotations

from academic_platform.infrastructure.search_providers.registry import (
    ProviderRegistry,
)
from academic_platform.infrastructure.search_providers.semantic_scholar.registration import (
    register_semantic_scholar,
)


def test_registration_adds_key() -> None:
    registry = ProviderRegistry()
    register_semantic_scholar(registry)
    assert "semantic_scholar" in registry


def test_registration_is_idempotent() -> None:
    registry = ProviderRegistry()
    register_semantic_scholar(registry)
    register_semantic_scholar(registry)
    assert registry.registered_keys().count("semantic_scholar") == 1


def test_default_registry_contains_semantic_scholar_after_import() -> None:
    import academic_platform.infrastructure.search_providers  # noqa: F401

    from academic_platform.infrastructure.search_providers.registry import (
        default_registry,
    )

    registry = default_registry()
    assert "semantic_scholar" in registry