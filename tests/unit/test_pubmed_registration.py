"""Tests for the PubMed registration helper."""

from __future__ import annotations

from academic_platform.infrastructure.search_providers.pubmed.registration import (
    register_pubmed,
)
from academic_platform.infrastructure.search_providers.registry import (
    ProviderRegistry,
)


def test_registration_adds_key() -> None:
    registry = ProviderRegistry()
    register_pubmed(registry)
    assert "pubmed" in registry


def test_registration_is_idempotent() -> None:
    registry = ProviderRegistry()
    register_pubmed(registry)
    register_pubmed(registry)
    assert registry.registered_keys().count("pubmed") == 1


def test_default_registry_contains_pubmed_after_import() -> None:
    import academic_platform.infrastructure.search_providers  # noqa: F401

    from academic_platform.infrastructure.search_providers.registry import (
        default_registry,
    )

    registry = default_registry()
    assert "pubmed" in registry