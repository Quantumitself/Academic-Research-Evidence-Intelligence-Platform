"""Tests for the search provider error hierarchy."""

from __future__ import annotations

from academic_platform.infrastructure.search_providers.errors import (
    ProviderConfigurationError,
    ProviderError,
    ProviderRequestError,
    ProviderResponseError,
    ProviderUnavailableError,
)


def test_hierarchy() -> None:
    assert issubclass(ProviderError, RuntimeError)
    assert issubclass(ProviderConfigurationError, ProviderError)
    assert issubclass(ProviderRequestError, ProviderError)
    assert issubclass(ProviderResponseError, ProviderError)
    assert issubclass(ProviderUnavailableError, ProviderError)