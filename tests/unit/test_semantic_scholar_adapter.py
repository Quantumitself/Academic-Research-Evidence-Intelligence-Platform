"""Tests for the Semantic Scholar adapter.

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
from academic_platform.infrastructure.search_providers.semantic_scholar.adapter import (
    SemanticScholarAdapter,
)


def _adapter(handler) -> SemanticScholarAdapter:
    transport = httpx.MockTransport(handler)
    config = HttpClientConfig(
        base_url="https://api.semanticscholar.org",
        max_retries=0,
    )
    client = HttpClient(config, transport=transport)
    return SemanticScholarAdapter(client)


def _success_payload() -> dict:
    return {
        "total": 2,
        "data": [
            {
                "paperId": "id-1",
                "title": "First",
                "year": 2020,
                "externalIds": {"DOI": "10.1000/one"},
            },
            {
                "paperId": "id-2",
                "title": "Second",
                "year": 2021,
                "externalIds": {"DOI": "10.1000/two"},
            },
        ],
    }


def test_descriptor() -> None:
    adapter = _adapter(lambda request: httpx.Response(200, json={}))
    descriptor = adapter.descriptor
    assert descriptor.key == "semantic_scholar"
    assert descriptor.capabilities.pagination is True
    assert descriptor.capabilities.abstract_in_results is True


def test_search_returns_hits() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=json.dumps(_success_payload()).encode("utf-8"),
            headers={"content-type": "application/json"},
        )

    adapter = _adapter(handler)
    response = adapter.search(SearchRequest(query="x"))
    assert response.provider_key == "semantic_scholar"
    assert len(response.hits) == 2
    assert response.total == 2
    assert response.status is not None
    assert response.status.status is SourceStatus.OK


def test_empty_request_is_skipped() -> None:
    adapter = _adapter(lambda request: httpx.Response(200, json={}))
    response = adapter.search(SearchRequest())
    assert response.hits == ()
    assert response.status is not None
    assert response.status.status is SourceStatus.SKIPPED


def test_date_asc_reverses_results() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=json.dumps(_success_payload()).encode("utf-8"),
            headers={"content-type": "application/json"},
        )

    adapter = _adapter(handler)
    response = adapter.search(SearchRequest(query="x", sort="date_asc"))
    assert response.hits[0].provider_identifier == "id-2"


def test_year_filter_forwarded() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        return httpx.Response(
            200,
            content=json.dumps(_success_payload()).encode("utf-8"),
            headers={"content-type": "application/json"},
        )

    adapter = _adapter(handler)
    adapter.search(SearchRequest(query="x", year_from=2010, year_to=2020))
    assert "year=2010-2020" in captured["url"]


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


def test_api_key_forwarded_when_supplied() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["api_key"] = request.headers.get("x-api-key")
        return httpx.Response(
            200,
            content=json.dumps(_success_payload()).encode("utf-8"),
            headers={"content-type": "application/json"},
        )

    transport = httpx.MockTransport(handler)
    config = HttpClientConfig(
        base_url="https://api.semanticscholar.org",
        max_retries=0,
        api_key="secret-key",
        api_key_header="x-api-key",
    )
    client = HttpClient(config, transport=transport)
    adapter = SemanticScholarAdapter(client)
    adapter.search(SearchRequest(query="x"))
    assert captured["api_key"] == "secret-key"