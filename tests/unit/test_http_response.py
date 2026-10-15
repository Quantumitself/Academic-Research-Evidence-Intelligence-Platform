"""Tests for the normalized HTTP response value object."""

from __future__ import annotations

from academic_platform.infrastructure.http.response import HttpResponse


def test_status_predicates() -> None:
    assert HttpResponse(status_code=200).is_success
    assert HttpResponse(status_code=301).is_redirect
    assert HttpResponse(status_code=404).is_client_error
    assert HttpResponse(status_code=500).is_server_error


def test_content_type_normalization() -> None:
    response = HttpResponse(
        status_code=200,
        headers=(("Content-Type", "Application/JSON; charset=utf-8"),),
    )
    assert response.content_type == "application/json"


def test_content_type_missing() -> None:
    assert HttpResponse(status_code=200).content_type == ""


def test_header_lookup_case_insensitive() -> None:
    response = HttpResponse(
        status_code=200,
        headers=(("X-Total-Count", "42"),),
    )
    assert response.header("x-total-count") == "42"
    assert response.header("missing", "fallback") == "fallback"


def test_text_decoding() -> None:
    response = HttpResponse(status_code=200, content=b"hello")
    assert response.text == "hello"


def test_text_replaces_invalid_bytes() -> None:
    response = HttpResponse(status_code=200, content=b"\xff\xfe")
    # The invalid bytes are replaced by the Unicode replacement character.
    assert "\ufffd" in response.text


def test_size_bytes() -> None:
    response = HttpResponse(status_code=200, content=b"abcdef")
    assert response.size_bytes == 6