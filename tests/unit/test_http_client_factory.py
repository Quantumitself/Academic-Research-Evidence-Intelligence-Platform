"""Tests for the HTTP client factory."""

from __future__ import annotations

import pytest

from academic_platform.application.search_sources.source_config import SourceConfig
from academic_platform.infrastructure.http.client import HttpClient
from academic_platform.infrastructure.http.factory import HttpClientFactory


def _config(**overrides) -> SourceConfig:
    defaults = {
        "key": "example",
        "provider_key": "example",
        "display_name": "Example",
        "source_type": "user_defined",
        "base_url": "https://api.example.invalid",
        "timeout_seconds": 25,
        "result_limit": 40,
    }
    defaults.update(overrides)
    return SourceConfig(**defaults)


def test_builds_client_with_defaults() -> None:
    factory = HttpClientFactory()
    client = factory.build(_config())
    try:
        assert isinstance(client, HttpClient)
        assert client.config.base_url == "https://api.example.invalid"
        assert client.config.read_timeout_seconds == 25.0
    finally:
        client.close()


def test_builds_with_bearer_token() -> None:
    factory = HttpClientFactory()
    client = factory.build(
        _config(auth_type="bearer_token", credential_reference="cred"),
        secret="secret-token",
    )
    try:
        assert client.config.bearer_token == "secret-token"
        assert client.config.api_key is None
    finally:
        client.close()


def test_builds_with_api_key() -> None:
    factory = HttpClientFactory()
    client = factory.build(
        _config(auth_type="api_key", credential_reference="cred"),
        secret="api-secret",
    )
    try:
        assert client.config.api_key == "api-secret"
        assert client.config.bearer_token is None
    finally:
        client.close()


def test_custom_user_agent() -> None:
    factory = HttpClientFactory(default_user_agent="Custom/1.0")
    client = factory.build(_config())
    try:
        assert client.config.user_agent == "Custom/1.0"
    finally:
        client.close()


def test_rate_limit_overrides() -> None:
    factory = HttpClientFactory()
    client = factory.build(
        _config(rate_limit={"requests_per_second": 2.0, "burst": 3})
    )
    try:
        assert client.config.rate_limit_per_second == 2.0
        assert client.config.rate_limit_burst == 3
    finally:
        client.close()


def test_allow_http_flag() -> None:
    factory = HttpClientFactory(allow_http=True)
    client = factory.build(_config(base_url="http://api.example.invalid"))
    try:
        assert client.config.allow_http is True
    finally:
        client.close()