"""Tests for the OpenAlex adapter.

The tests use ``httpx.MockTransport`` to avoid live network access.
"""

from __future__ import annotations

import json

import httpx
import pytest

from academic_platform.infrastructure.http.client import HttpClient
from academic_platform.infrastructure.http.config import HttpClientConfig
from academic_platform.infrastructure.search_providers.adapter import (
    SearchRequest,
    SourceStatus,
)
from academic_platform.infrastructure.search_providers.errors import (
    ProviderResponseError,
)
from academic_platform.infrastructure.search_providers.openalex.adapter import (
    OpenAlexAdapter,
)


def _adapter(handler, *, contact_email: str | None = None) -> OpenAlexAdapter:
    transport = httpx.MockTransport(handler)
    config = HttpClientConfig(
        base_url="https://api.openalex.org",
        max_retries=0,
    )
    client = HttpClient(config, transport=transport)
    return OpenAlexAdapter(client, contact_email=contact_email)


def _success_payload() -> dict:
    return {
        "meta": {"count": 2, "next_cursor": "cursor-next"},
        "results": [
            {
                "id": "https://openalex.org/W1",
                "doi": "https://doi.org/10.1000/one",
                "title": "First",
                "publication_year": 2020,
            },
            {
                "id": "https://openalex.org/W2",
                "doi": "https://doi.org/10.1000/two",
                "title": "Second",
                "publication_year": 2021,
            },
        ],
    }


def test_descriptor() -> None:
    adapter = _adapter(lambda request: httpx.Response(200, json={}))
    descriptor = adapter.descriptor
    assert descriptor.key == "openalex"
    assert descriptor.capabilities.pagination is True
    assert descriptor.capabilities.cursor_pagination is True
    assert descriptor.filters.open_access is True


def test_search_returns_hits() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=json.dumps(_success_payload()).encode("utf-8"),
            headers={"content-type": "application/json"},
        )

    adapter = _adapter(handler)
    response = adapter.search(SearchRequest(query="x"))
    assert response.provider_key == "openalex"
    assert len(response.hits) == 2
    assert response.total == 2
    assert response.next_cursor == "cursor-next"
    assert response.status is not None
    assert response.status.status is SourceStatus.OK


def test_empty_request_is_skipped() -> None:
    adapter = _adapter(lambda request: httpx.Response(200, json={}))
    response = adapter.search(SearchRequest())
    assert response.hits == ()
    assert response.status is not None
    assert response.status.status is SourceStatus.SKIPPED


def test_cursor_forwarded_in_request() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        return httpx.Response(
            200,
            content=json.dumps(_success_payload()).encode("utf-8"),
            headers={"content-type": "application/json"},
        )

    adapter = _adapter(handler)
    adapter.search(SearchRequest(query="x", cursor="cursor-abc"))
    assert "cursor=cursor-abc" in captured["url"]


def test_contact_email_added_to_request() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        return httpx.Response(
            200,
            content=json.dumps(_success_payload()).encode("utf-8"),
            headers={"content-type": "application/json"},
        )

    adapter = _adapter(handler, contact_email="user@example.invalid")
    adapter.search(SearchRequest(query="x"))
    assert "mailto=user%40example.invalid" in captured["url"]


def test_unparseable_response_raises() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=b"not json",
            headers={"content-type": "application/json"},
        )

    adapter = _adapter(handler)
    with pytest.raises(ProviderResponseError):
        adapter.search(SearchRequest(query="x"))


def test_test_connection_ok() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=json.dumps(_success_payload()).encode("utf-8"),
            headers={"content-type": "application/json"},
        )

    adapter = _adapter(handler)
    report = adapter.test_connection()
    assert report.status is SourceStatus.OK


def test_test_connection_reports_failure() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="error")

    adapter = _adapter(handler)
    report = adapter.test_connection()
    assert report.status is SourceStatus.FAILED
    assert report.message