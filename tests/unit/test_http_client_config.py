"""Tests for the HTTP client configuration value object."""

from __future__ import annotations

import pytest

from academic_platform.infrastructure.http.config import HttpClientConfig
from academic_platform.infrastructure.http.errors import (
    HttpClientConfigurationError,
)


def _base(**overrides) -> HttpClientConfig:
    defaults = {"base_url": "https://api.example.invalid"}
    defaults.update(overrides)
    return HttpClientConfig(**defaults)


def test_defaults() -> None:
    config = _base()
    assert config.connect_timeout_seconds == 10.0
    assert config.read_timeout_seconds == 30.0
    assert config.max_retries == 2
    assert config.allow_http is False
    assert config.verify_tls is True


def test_rejects_empty_base_url() -> None:
    with pytest.raises(HttpClientConfigurationError):
        HttpClientConfig(base_url="")


def test_rejects_nonpositive_timeout() -> None:
    with pytest.raises(HttpClientConfigurationError):
        _base(read_timeout_seconds=0)


def test_rejects_negative_retries() -> None:
    with pytest.raises(HttpClientConfigurationError):
        _base(max_retries=-1)


def test_rejects_backoff_inversion() -> None:
    with pytest.raises(HttpClientConfigurationError):
        _base(backoff_initial_seconds=4.0, backoff_max_seconds=1.0)


def test_rejects_nonpositive_size_limit() -> None:
    with pytest.raises(HttpClientConfigurationError):
        _base(max_response_bytes=0)


def test_rejects_negative_redirects() -> None:
    with pytest.raises(HttpClientConfigurationError):
        _base(max_redirects=-1)


def test_rejects_nonpositive_rate() -> None:
    with pytest.raises(HttpClientConfigurationError):
        _base(rate_limit_per_second=0)


def test_rejects_empty_content_types() -> None:
    with pytest.raises(HttpClientConfigurationError):
        _base(allowed_content_types=())


def test_rejects_empty_user_agent() -> None:
    with pytest.raises(HttpClientConfigurationError):
        _base(user_agent="   ")


def test_host_and_scheme() -> None:
    config = _base(base_url="https://api.example.invalid/path")
    assert config.host == "api.example.invalid"
    assert config.scheme == "https"


def test_with_overrides() -> None:
    config = _base()
    updated = config.with_overrides(read_timeout_seconds=5.0)
    assert updated.read_timeout_seconds == 5.0
    assert config.read_timeout_seconds == 30.0