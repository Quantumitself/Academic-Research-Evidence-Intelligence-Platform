"""Tests for the URL safety validator."""

from __future__ import annotations

import pytest

from academic_platform.infrastructure.search_providers.url_validator import (
    UrlRejection,
    validate_url,
)


def test_accepts_https_public_url() -> None:
    result = validate_url("https://api.crossref.org/works", resolve_host=False)
    assert result.ok is True
    assert result.host == "api.crossref.org"
    assert result.scheme == "https"


def test_rejects_http_by_default() -> None:
    result = validate_url("http://example.invalid", resolve_host=False)
    assert result.ok is False
    assert result.rejection is UrlRejection.UNSUPPORTED_SCHEME


def test_accepts_http_when_allowed() -> None:
    result = validate_url(
        "http://example.invalid",
        allow_http=True,
        resolve_host=False,
    )
    assert result.ok is True


def test_rejects_missing_scheme() -> None:
    result = validate_url("example.invalid", resolve_host=False)
    assert result.ok is False
    assert result.rejection is UrlRejection.MISSING_SCHEME


def test_rejects_empty_url() -> None:
    result = validate_url("   ", resolve_host=False)
    assert result.ok is False
    assert result.rejection is UrlRejection.EMPTY


def test_rejects_embedded_credentials() -> None:
    result = validate_url(
        "https://user:pass@example.invalid", resolve_host=False
    )
    assert result.ok is False
    assert result.rejection is UrlRejection.EMBEDDED_CREDENTIALS


def test_rejects_missing_host() -> None:
    result = validate_url("https:///path", resolve_host=False)
    assert result.ok is False
    assert result.rejection is UrlRejection.MISSING_HOST


def test_rejects_loopback_ip_literal_by_default() -> None:
    result = validate_url("https://127.0.0.1:8080", resolve_host=False)
    assert result.ok is False
    assert result.rejection is UrlRejection.LOOPBACK_NOT_ALLOWED


def test_accepts_loopback_when_allowed() -> None:
    result = validate_url(
        "https://127.0.0.1:8080",
        allow_loopback=True,
        resolve_host=False,
    )
    assert result.ok is True


def test_rejects_private_ip_literal() -> None:
    result = validate_url("https://10.0.0.1", resolve_host=False)
    assert result.ok is False
    assert result.rejection is UrlRejection.PRIVATE_ADDRESS


def test_rejects_link_local_ip_literal() -> None:
    result = validate_url("https://169.254.0.1", resolve_host=False)
    assert result.ok is False
    assert result.rejection in {
        UrlRejection.LINK_LOCAL_ADDRESS,
        UrlRejection.METADATA_ADDRESS,
    }


def test_rejects_cloud_metadata_ip() -> None:
    result = validate_url("https://169.254.169.254", resolve_host=False)
    assert result.ok is False
    assert result.rejection is UrlRejection.METADATA_ADDRESS


def test_rejects_ipv6_loopback() -> None:
    result = validate_url("https://[::1]:8080", resolve_host=False)
    assert result.ok is False
    assert result.rejection is UrlRejection.LOOPBACK_NOT_ALLOWED


def test_accepts_public_ip_literal() -> None:
    result = validate_url("https://93.184.216.34", resolve_host=False)
    assert result.ok is True


def test_resolution_failure_reported() -> None:
    result = validate_url(
        "https://does-not-exist.invalid",
        resolve_host=True,
    )
    assert result.ok is False
    assert result.rejection is UrlRejection.RESOLUTION_FAILED