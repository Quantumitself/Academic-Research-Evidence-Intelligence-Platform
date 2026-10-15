"""Tests for the arXiv adapter.

The tests use ``httpx.MockTransport`` to avoid live network access.
"""

from __future__ import annotations

import httpx
import pytest

from academic_platform.infrastructure.http.client import HttpClient
from academic_platform.infrastructure.http.config import HttpClientConfig
from academic_platform.infrastructure.search_providers.adapter import (
    SearchRequest,
    SourceStatus,
)
from academic_platform.infrastructure.search_providers.arxiv.adapter import (
    ArxivAdapter,
)
from academic_platform.infrastructure.search_providers.errors import (
    ProviderResponseError,
)


def _adapter(handler) -> ArxivAdapter:
    transport = httpx.MockTransport(handler)
    config = HttpClientConfig(
        base_url="https://export.arxiv.org",
        max_retries=0,
        allowed_content_types=(
            "application/json",
            "application/xml",
            "application/atom+xml",
            "text/xml",
            "text/plain",
        ),
    )
    client = HttpClient(config, transport=transport)
    return ArxivAdapter(client)


def _success_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"
      xmlns:opensearch="http://a9.com/-/spec/opensearch/1.1/"
      xmlns:arxiv="http://arxiv.org/schemas/atom">
  <opensearch:totalResults>2</opensearch:totalResults>
  <opensearch:itemsPerPage>10</opensearch:itemsPerPage>
  <entry>
    <id>http://arxiv.org/abs/2401.1</id>
    <published>2024-01-01T00:00:00Z</published>
    <title>First</title>
    <summary>First abstract.</summary>
    <author><name>A</name></author>
    <arxiv:primary_category term="cs.LG" />
  </entry>
  <entry>
    <id>http://arxiv.org/abs/2401.2</id>
    <published>2024-02-01T00:00:00Z</published>
    <title>Second</title>
    <summary>Second abstract.</summary>
    <author><name>B</name></author>
    <arxiv:primary_category term="cs.AI" />
  </entry>
</feed>"""


def test_descriptor() -> None:
    adapter = _adapter(lambda request: httpx.Response(200, text=""))
    descriptor = adapter.descriptor
    assert descriptor.key == "arxiv"
    assert descriptor.filters.author is True
    assert descriptor.capabilities.abstract_in_results is True


def test_search_returns_hits() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=_success_xml().encode("utf-8"),
            headers={"content-type": "application/atom+xml"},
        )

    adapter = _adapter(handler)
    response = adapter.search(SearchRequest(query="x"))
    assert response.provider_key == "arxiv"
    assert len(response.hits) == 2
    assert response.total == 2
    assert response.status is not None
    assert response.status.status is SourceStatus.OK


def test_empty_request_is_skipped() -> None:
    adapter = _adapter(lambda request: httpx.Response(200, text=""))
    response = adapter.search(SearchRequest())
    assert response.hits == ()
    assert response.status is not None
    assert response.status.status is SourceStatus.SKIPPED


def test_sort_date_asc_forwarded_in_request() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        return httpx.Response(
            200,
            content=_success_xml().encode("utf-8"),
            headers={"content-type": "application/atom+xml"},
        )

    adapter = _adapter(handler)
    adapter.search(SearchRequest(query="x", sort="date_asc"))
    assert "sortBy=submittedDate" in captured["url"]
    assert "sortOrder=ascending" in captured["url"]


def test_unparseable_response_raises() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=b"not xml",
            headers={"content-type": "application/atom+xml"},
        )

    adapter = _adapter(handler)
    with pytest.raises(ProviderResponseError):
        adapter.search(SearchRequest(query="x"))


def test_test_connection_ok() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=_success_xml().encode("utf-8"),
            headers={"content-type": "application/atom+xml"},
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