"""Tests for the arXiv response parser."""

from __future__ import annotations

import pytest

from academic_platform.infrastructure.search_providers.arxiv.parser import (
    ArxivResponseParser,
)
from academic_platform.infrastructure.search_providers.errors import (
    ProviderResponseError,
)


def _parser() -> ArxivResponseParser:
    return ArxivResponseParser()


def _wrap_entries(*entries: str) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"
      xmlns:opensearch="http://a9.com/-/spec/opensearch/1.1/"
      xmlns:arxiv="http://arxiv.org/schemas/atom">
  <opensearch:totalResults xmlns:opensearch="http://a9.com/-/spec/opensearch/1.1/">{len(entries)}</opensearch:totalResults>
  <opensearch:itemsPerPage xmlns:opensearch="http://a9.com/-/spec/opensearch/1.1/">10</opensearch:itemsPerPage>
  {"".join(entries)}
</feed>"""


def _entry(**overrides) -> str:
    default = """
  <entry>
    <id>http://arxiv.org/abs/2401.12345v1</id>
    <published>2024-01-15T12:00:00Z</published>
    <title>A Title</title>
    <summary>An abstract.</summary>
    <author><name>Author A</name></author>
    <author><name>Author B</name></author>
    <arxiv:primary_category term="cs.LG" />
    <arxiv:doi>10.1000/XYZ</arxiv:doi>
  </entry>
"""
    for key, value in overrides.items():
        placeholder = f"<{key}>"
        # Simple string replacement; tests only override textual values.
        if key == "title":
            default = default.replace("<title>A Title</title>", f"<title>{value}</title>")
        elif key == "summary":
            default = default.replace(
                "<summary>An abstract.</summary>", f"<summary>{value}</summary>"
            )
        elif key == "primary_category":
            default = default.replace(
                '<arxiv:primary_category term="cs.LG" />',
                f'<arxiv:primary_category term="{value}" />',
            )
    return default


def test_parse_minimal_feed() -> None:
    payload = _wrap_entries(_entry())
    hits, total, items_per_page = _parser().parse(payload)
    assert total == 1
    assert items_per_page == 10
    assert len(hits) == 1
    hit = hits[0]
    assert hit.provider_key == "arxiv"
    assert hit.provider_identifier == "2401.12345v1"
    assert hit.title == "A Title"
    assert hit.abstract == "An abstract."
    assert hit.year == 2024
    assert hit.authors == ("Author A", "Author B")
    assert hit.venue == "cs.LG"
    assert hit.doi == "10.1000/xyz"
    assert hit.is_open_access is True
    assert hit.url == "http://arxiv.org/abs/2401.12345v1"


def test_parse_raises_on_empty_payload() -> None:
    with pytest.raises(ProviderResponseError):
        _parser().parse("")


def test_parse_raises_on_invalid_xml() -> None:
    with pytest.raises(ProviderResponseError):
        _parser().parse("<not valid xml")


def test_parse_raises_on_wrong_root() -> None:
    with pytest.raises(ProviderResponseError):
        _parser().parse("<rss></rss>")


def test_parse_skips_entries_without_id() -> None:
    entry_without_id = """
  <entry>
    <title>No ID</title>
    <summary>Summary.</summary>
  </entry>
"""
    payload = _wrap_entries(entry_without_id)
    hits, _, _ = _parser().parse(payload)
    assert hits == []


def test_parse_handles_missing_doi() -> None:
    entry = _entry()
    entry = entry.replace("<arxiv:doi>10.1000/XYZ</arxiv:doi>", "")
    payload = _wrap_entries(entry)
    hits, _, _ = _parser().parse(payload)
    assert hits[0].doi is None


def test_parse_multiple_entries() -> None:
    payload = _wrap_entries(_entry(), _entry())
    hits, _, _ = _parser().parse(payload)
    assert len(hits) == 2


def test_primary_category_from_first_when_primary_missing() -> None:
    entry = _entry()
    entry = entry.replace('<arxiv:primary_category term="cs.LG" />', "")
    entry = entry.replace(
        "</entry>",
        '<category term="math.CO" /></entry>',
    )
    payload = _wrap_entries(entry)
    hits, _, _ = _parser().parse(payload)
    assert hits[0].venue == "math.CO"