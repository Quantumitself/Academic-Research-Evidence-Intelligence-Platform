"""Tests for the Europe PMC adapter.

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
from academic_platform.infrastructure.search_providers.europe_pmc.adapter import (
    EuropePmcAdapter,
)


def _adapter(handler) -> EuropePmcAdapter:
    transport = httpx.MockTransport(handler)
    config = HttpClientConfig(
        base_url="https://www.ebi.ac.uk",
        max_retries=0,
    )
    client = HttpClient(config, transport=transport)
    return EuropePmcAdapter(client)


def _success_payload() -> dict:
    return {
        "hitCount": 2,
        "nextCursorMark": "next-cursor",
        "resultList": {
            "result": [
                {
                    "id": "id-1",
                    "doi": "10.1000/one",
                    "title": "First",
                    "pubYear": "2020",
                },
                {
                    "id": "id-2",
                    "doi": "10.1000/two",
                    "title": "Second",
                    "pubYear": "2021",
                },
            ]
        },
    }


def test_descriptor() -> None:
    adapter = _adapter(lambda request: httpx.Response(200, json={}))
    descriptor = adapter.descriptor
    assert descriptor.key == "europe_pmc"
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
    assert response.provider_key == "europe_pmc"
    assert len(response.hits) == 2
    assert response.total == 2
    assert response.next_cursor == "next-cursor"
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
    assert "cursorMark=cursor-abc" in captured["url"]


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
            content=json.dumps({"hitCount": 0}).encode("utf-8"),
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