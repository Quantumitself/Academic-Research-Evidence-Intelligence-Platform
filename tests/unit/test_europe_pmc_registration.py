"""Tests for the Europe PMC registration helper."""

from __future__ import annotations

from academic_platform.infrastructure.search_providers.europe_pmc.registration import (
    register_europe_pmc,
)
from academic_platform.infrastructure.search_providers.registry import (
    ProviderRegistry,
)


def test_registration_adds_key() -> None:
    registry = ProviderRegistry()
    register_europe_pmc(registry)
    assert "europe_pmc" in registry


def test_registration_is_idempotent() -> None:
    registry = ProviderRegistry()
    register_europe_pmc(registry)
    register_europe_pmc(registry)
    assert registry.registered_keys().count("europe_pmc") == 1


def test_default_registry_contains_europe_pmc_after_import() -> None:
    import academic_platform.infrastructure.search_providers  # noqa: F401

    from academic_platform.infrastructure.search_providers.registry import (
        default_registry,
    )

    registry = default_registry()
    assert "europe_pmc" in registry