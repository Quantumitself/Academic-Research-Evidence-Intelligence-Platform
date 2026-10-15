"""Tests for the HTTP client.

The tests use ``httpx.MockTransport`` to avoid any real network access.
The mock transport returns deterministic responses so that retry and
size-limit behaviour can be verified without a live provider.
"""

from __future__ import annotations

import httpx
import pytest

from academic_platform.infrastructure.http.client import HttpClient
from academic_platform.infrastructure.http.config import HttpClientConfig
from academic_platform.infrastructure.http.errors import (
    HttpClientConfigurationError,
    HttpClientNetworkError,
    HttpClientResponseError,
    HttpClientSizeLimitError,
    HttpClientTimeoutError,
)


def _config(**overrides) -> HttpClientConfig:
    defaults = {
        "base_url": "https://api.example.invalid",
        "max_retries": 2,
        "backoff_initial_seconds": 0.001,
        "backoff_max_seconds": 0.01,
        "validate_destination": False,
    }
    defaults.update(overrides)
    return HttpClientConfig(**defaults)


def _client(handler, **overrides) -> HttpClient:
    transport = httpx.MockTransport(handler)
    return HttpClient(_config(**overrides), transport=transport)


def test_successful_get() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"hello": "world"},
            headers={"content-type": "application/json"},
        )

    with _client(handler) as client:
        response = client.get("https://api.example.invalid/works")
        assert response.status_code == 200
        assert response.content_type == "application/json"
        assert response.text


def test_timeout_is_wrapped() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("boom", request=request)

    with _client(handler) as client:
        with pytest.raises(HttpClientTimeoutError):
            client.get("https://api.example.invalid/works")


def test_network_error_is_wrapped() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom", request=request)

    with _client(handler) as client:
        with pytest.raises(HttpClientNetworkError):
            client.get("https://api.example.invalid/works")


def test_retry_on_transient_status_then_success() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] < 3:
            return httpx.Response(503, text="retry")
        return httpx.Response(200, json={"ok": True})

    with _client(handler) as client:
        response = client.get("https://api.example.invalid/works")
        assert response.status_code == 200
        assert calls["n"] == 3


def test_retry_exhausted_raises() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(503, text="retry")

    with _client(handler, max_retries=1) as client:
        response = client.get("https://api.example.invalid/works")
        assert response.status_code == 503
        assert calls["n"] == 2


def test_retry_not_applied_to_post() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(503, text="retry")

    with _client(handler) as client:
        response = client.post("https://api.example.invalid/works")
        assert response.status_code == 503
        assert calls["n"] == 1


def test_non_transient_status_raises() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, text="not found")

    with _client(handler) as client:
        with pytest.raises(HttpClientResponseError):
            client.get("https://api.example.invalid/works")


def test_content_type_enforced() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=b"binary",
            headers={"content-type": "application/octet-stream"},
        )

    with _client(handler) as client:
        with pytest.raises(HttpClientResponseError):
            client.get("https://api.example.invalid/works")


def test_size_limit_enforced() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=b"x" * 2048,
            headers={"content-type": "text/plain"},
        )

    with _client(handler, max_response_bytes=1024) as client:
        with pytest.raises(HttpClientSizeLimitError):
            client.get("https://api.example.invalid/works")


def test_rejects_json_and_data_together() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200)

    with _client(handler) as client:
        with pytest.raises(HttpClientConfigurationError):
            client.request(
                "POST",
                "https://api.example.invalid/works",
                json={"a": 1},
                data={"b": 2},
            )


def test_rejects_private_destination_when_enabled() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200)

    transport = httpx.MockTransport(handler)
    config = HttpClientConfig(
        base_url="https://api.example.invalid",
        validate_destination=True,
    )
    with HttpClient(config, transport=transport) as client:
        with pytest.raises(HttpClientConfigurationError):
            client.get("https://10.0.0.1/works")


def test_injects_bearer_token() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["authorization"] = request.headers.get("authorization")
        return httpx.Response(200, json={})

    with _client(handler, bearer_token="secret") as client:
        client.get("https://api.example.invalid/works")
    assert captured["authorization"] == "Bearer secret"


def test_injects_api_key_header() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["key"] = request.headers.get("x-api-key")
        return httpx.Response(200, json={})

    with _client(handler, api_key="secret", api_key_header="X-API-Key") as client:
        client.get("https://api.example.invalid/works")
    assert captured["key"] == "secret"


def test_headers_default_applied() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["ua"] = request.headers.get("user-agent")
        captured["accept"] = request.headers.get("accept")
        return httpx.Response(200, json={})

    with _client(handler) as client:
        client.get("https://api.example.invalid/works")
    assert captured["ua"]
    assert captured["accept"]

def test_rejects_private_destination_when_validation_enabled() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={})

    transport = httpx.MockTransport(handler)
    config = HttpClientConfig(
        base_url="https://10.0.0.1",
        validate_destination=True,
    )
    with HttpClient(config, transport=transport) as client:
        with pytest.raises(HttpClientConfigurationError):
            client.get("https://10.0.0.1/works")