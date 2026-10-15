"""Tests for the arXiv registration helper."""

from __future__ import annotations

from academic_platform.infrastructure.search_providers.arxiv.registration import (
    register_arxiv,
)
from academic_platform.infrastructure.search_providers.registry import (
    ProviderRegistry,
)


def test_registration_adds_key() -> None:
    registry = ProviderRegistry()
    register_arxiv(registry)
    assert "arxiv" in registry


def test_registration_is_idempotent() -> None:
    registry = ProviderRegistry()
    register_arxiv(registry)
    register_arxiv(registry)
    assert registry.registered_keys().count("arxiv") == 1


def test_default_registry_contains_arxiv_after_import() -> None:
    import academic_platform.infrastructure.search_providers  # noqa: F401

    from academic_platform.infrastructure.search_providers.registry import (
        default_registry,
    )

    registry = default_registry()
    assert "arxiv" in registry