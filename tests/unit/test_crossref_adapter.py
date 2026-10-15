"""Tests for the Crossref adapter.

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
from academic_platform.infrastructure.search_providers.crossref.adapter import (
    CrossrefAdapter,
)
from academic_platform.infrastructure.search_providers.errors import (
    ProviderResponseError,
    ProviderUnavailableError,
)


def _adapter(handler) -> CrossrefAdapter:
    transport = httpx.MockTransport(handler)
    config = HttpClientConfig(
        base_url="https://api.crossref.org",
        max_retries=0,
    )
    client = HttpClient(config, transport=transport)
    return CrossrefAdapter(client)


def _success_payload() -> dict:
    return {
        "message": {
            "total-results": 2,
            "items": [
                {
                    "DOI": "10.1000/one",
                    "title": ["First"],
                    "issued": {"date-parts": [[2020]]},
                },
                {
                    "DOI": "10.1000/two",
                    "title": ["Second"],
                    "issued": {"date-parts": [[2021]]},
                },
            ],
        }
    }


def test_descriptor() -> None:
    adapter = _adapter(lambda request: httpx.Response(200, json={}))
    descriptor = adapter.descriptor
    assert descriptor.key == "crossref"
    assert descriptor.capabilities.pagination is True
    assert descriptor.filters.year_range is True


def test_search_returns_hits() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=json.dumps(_success_payload()).encode("utf-8"),
            headers={"content-type": "application/json"},
        )

    adapter = _adapter(handler)
    response = adapter.search(SearchRequest(query="x"))
    assert response.provider_key == "crossref"
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
    # The parser preserves provider order; the adapter reverses when
    # date_asc is requested.
    assert response.hits[0].provider_identifier == "10.1000/two"


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


def test_transient_status_raises_unavailable() -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(503, text="unavailable")

    adapter = _adapter(handler)
    with pytest.raises(ProviderResponseError):
        adapter.search(SearchRequest(query="x"))
    assert calls["n"] == 1


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