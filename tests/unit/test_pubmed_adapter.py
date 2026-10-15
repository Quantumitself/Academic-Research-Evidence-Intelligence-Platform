"""Tests for the PubMed adapter.

The tests use ``httpx.MockTransport`` and route requests to the three
E-utilities endpoints.
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
from academic_platform.infrastructure.search_providers.pubmed.adapter import (
    PubMedAdapter,
)


def _adapter(handler, *, fetch_abstracts: bool = True) -> PubMedAdapter:
    transport = httpx.MockTransport(handler)
    config = HttpClientConfig(
        base_url="https://eutils.ncbi.nlm.nih.gov",
        max_retries=0,
    )
    client = HttpClient(config, transport=transport)
    return PubMedAdapter(client, fetch_abstracts=fetch_abstracts)


def _search_payload() -> dict:
    return {"esearchresult": {"count": "2", "idlist": ["111", "222"]}}


def _summary_payload() -> dict:
    return {
        "result": {
            "uids": ["111", "222"],
            "111": {
                "uid": "111",
                "title": "First",
                "authors": [{"name": "A"}],
                "pubdate": "2020",
                "fulljournalname": "J",
                "articleids": [{"idtype": "doi", "value": "10.1000/one"}],
            },
            "222": {
                "uid": "222",
                "title": "Second",
                "authors": [{"name": "B"}],
                "pubdate": "2021",
                "fulljournalname": "J",
                "articleids": [{"idtype": "doi", "value": "10.1000/two"}],
            },
        }
    }


def _fetch_payload() -> dict:
    return {
        "result": {
            "uids": ["111", "222"],
            "111": {"abstract": "First abstract."},
            "222": {"abstract": "Second abstract."},
        }
    }


def _router(*, search=None, summary=None, fetch=None) -> callable:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if "esearch" in path:
            body = search if search is not None else _search_payload()
        elif "esummary" in path:
            body = summary if summary is not None else _summary_payload()
        elif "efetch" in path:
            body = fetch if fetch is not None else _fetch_payload()
        else:
            return httpx.Response(404, text="not found")
        return httpx.Response(
            200,
            content=json.dumps(body).encode("utf-8"),
            headers={"content-type": "application/json"},
        )

    return handler


def test_descriptor() -> None:
    adapter = _adapter(_router())
    descriptor = adapter.descriptor
    assert descriptor.key == "pubmed"
    assert descriptor.capabilities.pagination is True


def test_search_composes_calls() -> None:
    adapter = _adapter(_router())
    response = adapter.search(SearchRequest(query="ml", limit=10))
    assert response.provider_key == "pubmed"
    assert len(response.hits) == 2
    assert response.hits[0].abstract == "First abstract."
    assert response.hits[1].abstract == "Second abstract."
    assert response.total == 2
    assert response.status is not None
    assert response.status.status is SourceStatus.OK


def test_empty_request_is_skipped() -> None:
    adapter = _adapter(_router())
    response = adapter.search(SearchRequest())
    assert response.hits == ()
    assert response.status is not None
    assert response.status.status is SourceStatus.SKIPPED


def test_search_with_no_matches() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=json.dumps(
                {"esearchresult": {"count": "0", "idlist": []}}
            ).encode("utf-8"),
            headers={"content-type": "application/json"},
        )

    adapter = _adapter(handler)
    response = adapter.search(SearchRequest(query="nothing"))
    assert response.hits == ()
    assert response.total == 0
    assert response.status is not None
    assert response.status.status is SourceStatus.OK


def test_abstract_fetch_failure_returns_hits_without_abstracts() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if "esearch" in path:
            return httpx.Response(
                200,
                content=json.dumps(_search_payload()).encode("utf-8"),
                headers={"content-type": "application/json"},
            )
        if "esummary" in path:
            return httpx.Response(
                200,
                content=json.dumps(_summary_payload()).encode("utf-8"),
                headers={"content-type": "application/json"},
            )
        # Simulate an efetch failure.
        return httpx.Response(500, text="error")

    adapter = _adapter(handler)
    response = adapter.search(SearchRequest(query="ml"))
    assert len(response.hits) == 2
    assert response.hits[0].abstract == ""


def test_fetch_abstracts_disabled() -> None:
    adapter = _adapter(_router(), fetch_abstracts=False)
    response = adapter.search(SearchRequest(query="ml"))
    assert response.hits[0].abstract == ""


def test_unparseable_response_raises() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=b"not json",
            headers={"content-type": "application/json"},
        )

    adapter = _adapter(handler)
    with pytest.raises(ProviderResponseError):
        adapter.search(SearchRequest(query="ml"))


def test_test_connection_ok() -> None:
    adapter = _adapter(_router())
    report = adapter.test_connection()
    assert report.status is SourceStatus.OK


def test_test_connection_reports_failure() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="error")

    adapter = _adapter(handler)
    report = adapter.test_connection()
    assert report.status is SourceStatus.FAILED