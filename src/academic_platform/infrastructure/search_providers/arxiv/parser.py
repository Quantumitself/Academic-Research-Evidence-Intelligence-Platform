"""Parsing of arXiv Atom responses into provider-neutral hits.

arXiv returns Atom XML. The parser is a self-contained, standards-aware
extractor that uses the standard library's ``xml.etree.ElementTree``.
It deliberately does not attempt to implement a general-purpose XML
processor; it extracts the fields the application uses and ignores the
rest.

Design decisions
----------------
- The parser never raises on a missing optional field. It substitutes a
  neutral value and continues.
- The parser raises ``ProviderResponseError`` only when the top-level
  structure is not what arXiv documents (a missing ``feed`` element).
- Individual malformed entries are skipped with a warning. A single bad
  entry never invalidates a response.
- Namespaces are handled explicitly. arXiv uses the Atom namespace for
  the feed and entry elements, the OpenSearch namespace for pagination
  metadata, and the arXiv namespace for the primary category and
  identifier.
- The parser converts the arXiv identifier to a canonical form. arXiv
  entries carry an ``id`` element that contains a URL; the parser
  extracts the trailing identifier.
- Authors are extracted from the ``author/name`` structure.
- The abstract is taken from the ``summary`` element and normalized.
- The published date is taken from the ``published`` element and reduced
  to a four-digit year.
"""

from __future__ import annotations

import logging
import re
from typing import Any
from xml.etree import ElementTree as ET

from academic_platform.infrastructure.search_providers.adapter import (
    SearchHit,
)
from academic_platform.infrastructure.search_providers.errors import (
    ProviderResponseError,
)

_logger = logging.getLogger(__name__)

_ATOM_NS = "http://www.w3.org/2005/Atom"
_OPENSEARCH_NS = "http://a9.com/-/spec/opensearch/1.1/"
_ARXIV_NS = "http://arxiv.org/schemas/atom"

_WHITESPACE_PATTERN = re.compile(r"\s+")


class ArxivResponseParser:
    """Parse arXiv Atom responses into provider-neutral hits."""

    def __init__(self, provider_key: str = "arxiv") -> None:
        self._provider_key = provider_key

    @property
    def provider_key(self) -> str:
        return self._provider_key

    def parse(
        self,
        payload: str,
    ) -> tuple[list[SearchHit], int | None, int | None]:
        """Parse an arXiv Atom response.

        Parameters
        ----------
        payload:
            The raw XML text of the response.

        Returns
        -------
        tuple[list[SearchHit], int | None, int | None]
            The parsed hits, the total number of matching records
            (``opensearch:totalResults``), and the number of results per
            page (``opensearch:itemsPerPage``). The provider does not
            return a cursor; the caller derives the next offset from the
            number of hits returned and the ``start`` parameter.
        """
        if not payload or not payload.strip():
            raise ProviderResponseError("arXiv response is empty")
        try:
            root = ET.fromstring(payload)
        except ET.ParseError as exc:
            raise ProviderResponseError(
                f"arXiv response is not valid XML: {exc}"
            ) from exc
        if _local_name(root.tag) != "feed":
            raise ProviderResponseError(
                "arXiv response root element is not 'feed'"
            )

        total = self._opensearch_total(root)
        items_per_page = self._opensearch_items_per_page(root)

        hits: list[SearchHit] = []
        for index, entry in enumerate(root.findall(_atom("entry"))):
            try:
                hit = self._parse_entry(entry)
            except Exception as exc:  # noqa: BLE001 - boundary
                _logger.warning(
                    "Skipping malformed arXiv entry at index %d: %s",
                    index,
                    exc,
                )
                continue
            if hit is not None:
                hits.append(hit)
        return hits, total, items_per_page

    # ------------------------------------------------------------------
    # OpenSearch metadata
    # ------------------------------------------------------------------
    def _opensearch_total(self, root: ET.Element) -> int | None:
        value = root.findtext(_opensearch("totalResults"))
        if value and value.isdigit():
            return int(value)
        return None

    def _opensearch_items_per_page(self, root: ET.Element) -> int | None:
        value = root.findtext(_opensearch("itemsPerPage"))
        if value and value.isdigit():
            return int(value)
        return None

    # ------------------------------------------------------------------
    # Entry parsing
    # ------------------------------------------------------------------
    def _parse_entry(self, entry: ET.Element) -> SearchHit | None:
        identifier = self._identifier(entry)
        if not identifier:
            return None
        title = self._text(entry, "title")
        abstract = self._text(entry, "summary")
        authors = self._authors(entry)
        year = self._year(entry)
        venue = self._primary_category(entry)
        doi = self._doi(entry)
        language = None
        is_open_access = True  # arXiv preprints are openly available
        url = self._url(entry, identifier)
        return SearchHit(
            provider_key=self._provider_key,
            provider_identifier=identifier,
            title=_normalize_whitespace(title),
            abstract=_normalize_whitespace(abstract),
            authors=authors,
            year=year,
            venue=venue,
            doi=doi,
            language=language,
            is_open_access=is_open_access,
            citation_count=None,
            url=url,
            score=None,
            extra={
                "arxiv_id": identifier,
                "primary_category": venue,
            },
        )

    def _identifier(self, entry: ET.Element) -> str:
        raw = entry.findtext(_atom("id"))
        if not raw:
            return ""
        # arXiv returns ids of the form http://arxiv.org/abs/XXXX.YYYYYvN
        stripped = raw.strip()
        if "/abs/" in stripped:
            return stripped.rsplit("/abs/", 1)[-1]
        return stripped

    def _text(self, entry: ET.Element, local: str) -> str:
        value = entry.findtext(_atom(local))
        return value.strip() if value else ""

    def _authors(self, entry: ET.Element) -> tuple[str, ...]:
        results: list[str] = []
        for author in entry.findall(_atom("author")):
            name = author.findtext(_atom("name"))
            if name:
                cleaned = _normalize_whitespace(name.strip())
                if cleaned:
                    results.append(cleaned)
        return tuple(results)

    def _year(self, entry: ET.Element) -> int | None:
        published = entry.findtext(_atom("published"))
        if published and len(published) >= 4:
            candidate = published[:4]
            if candidate.isdigit():
                return int(candidate)
        updated = entry.findtext(_atom("updated"))
        if updated and len(updated) >= 4:
            candidate = updated[:4]
            if candidate.isdigit():
                return int(candidate)
        return None

    def _primary_category(self, entry: ET.Element) -> str:
        category = entry.find(_arxiv("primary_category"))
        if category is not None:
            term = category.attrib.get("term")
            if term:
                return term
        # Fall back to the first top-level category element.
        for cat in entry.findall(_atom("category")):
            term = cat.attrib.get("term")
            if term:
                return term
        return ""

    def _doi(self, entry: ET.Element) -> str | None:
        value = entry.findtext(_arxiv("doi"))
        if value and value.strip():
            return value.strip().lower()
        return None

    def _url(self, entry: ET.Element, identifier: str) -> str | None:
        raw = entry.findtext(_atom("id"))
        if raw and raw.strip():
            return raw.strip()
        if identifier:
            return f"https://arxiv.org/abs/{identifier}"
        return None


def _atom(local: str) -> str:
    return f"{{{_ATOM_NS}}}{local}"


def _opensearch(local: str) -> str:
    return f"{{{_OPENSEARCH_NS}}}{local}"


def _arxiv(local: str) -> str:
    return f"{{{_ARXIV_NS}}}{local}"


def _local_name(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[-1]
    return tag


def _normalize_whitespace(value: str) -> str:
    return _WHITESPACE_PATTERN.sub(" ", value).strip()