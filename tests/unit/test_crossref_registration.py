"""Tests for the Crossref registration helper."""

from __future__ import annotations

from academic_platform.infrastructure.search_providers.crossref.registration import (
    register_crossref,
)
from academic_platform.infrastructure.search_providers.registry import (
    ProviderRegistry,
)


def test_registration_adds_key() -> None:
    registry = ProviderRegistry()
    register_crossref(registry)
    assert "crossref" in registry


def test_registration_is_idempotent() -> None:
    registry = ProviderRegistry()
    register_crossref(registry)
    register_crossref(registry)
    assert registry.registered_keys().count("crossref") == 1


def test_default_registry_contains_crossref_after_import() -> None:
    # Importing the search providers package registers the Crossref
    # adapter with the default registry.
    import academic_platform.infrastructure.search_providers  # noqa: F401

    from academic_platform.infrastructure.search_providers.registry import (
        default_registry,
    )

    registry = default_registry()
    assert "crossref" in registry