"""Parsing of Crossref responses into provider-neutral hits.

The parser is deliberately defensive: Crossref's schema has evolved over
time, and different works carry different subsets of fields. The parser
extracts the fields the application uses and ignores the rest.

Design decisions
----------------
- The parser never raises on a missing optional field. It substitutes a
  neutral value (empty string, ``None``) and continues.
- The parser raises ``ProviderResponseError`` only when the top-level
  structure is not what Crossref documents. Individual malformed items
  are skipped with a warning so that a single bad item does not
  invalidate the whole response.
- Author lists are normalized to a tuple of display strings. Given and
  family names are combined when both are present; a missing given name
  or family name yields the other.
- The DOI is stored as-is. Crossref returns DOIs in lowercase; the
  parser normalizes to lowercase to match the application's convention.
- The abstract is extracted when Crossref includes it. Crossref returns
  abstracts as JATS XML; the parser strips the XML tags and decodes the
  character entities that remain. This is a lossy transformation, and
  the parser documents that limitation.
"""

from __future__ import annotations

import html
import logging
import re
from typing import Any

from academic_platform.infrastructure.search_providers.adapter import (
    SearchHit,
)
from academic_platform.infrastructure.search_providers.errors import (
    ProviderResponseError,
)

_logger = logging.getLogger(__name__)

_JATS_TAG_PATTERN = re.compile(r"<[^>]+>")
_WHITESPACE_PATTERN = re.compile(r"\s+")


class CrossrefResponseParser:
    """Parse Crossref response payloads into provider-neutral hits."""

    def __init__(self, provider_key: str = "crossref") -> None:
        self._provider_key = provider_key

    @property
    def provider_key(self) -> str:
        return self._provider_key

    def parse(self, payload: dict[str, Any]) -> tuple[list[SearchHit], int | None, str | None]:
        """Parse a Crossref response.

        Returns
        -------
        tuple[list[SearchHit], int | None, str | None]
            The parsed hits, the total number of matching works reported
            by Crossref (``message.total-results``), and the next cursor
            (``None``; Crossref does not use cursor pagination).
        """
        if not isinstance(payload, dict):
            raise ProviderResponseError("Crossref response is not a JSON object")
        message = payload.get("message")
        if not isinstance(message, dict):
            raise ProviderResponseError(
                "Crossref response is missing the 'message' object"
            )
        items = message.get("items")
        if not isinstance(items, list):
            raise ProviderResponseError(
                "Crossref response is missing the 'items' list"
            )
        total = message.get("total-results")
        total_int = int(total) if isinstance(total, int) else None

        hits: list[SearchHit] = []
        for index, item in enumerate(items):
            try:
                hit = self._parse_item(item)
            except Exception as exc:  # noqa: BLE001 - boundary
                _logger.warning(
                    "Skipping malformed Crossref item at index %d: %s", index, exc
                )
                continue
            if hit is not None:
                hits.append(hit)
        return hits, total_int, None

    # ------------------------------------------------------------------
    # Item parsing
    # ------------------------------------------------------------------
    def _parse_item(self, item: Any) -> SearchHit | None:
        if not isinstance(item, dict):
            return None
        identifier = self._identifier(item)
        if not identifier:
            return None
        title = self._first_title(item)
        authors = self._authors(item)
        year = self._year(item)
        venue = self._first_container_title(item)
        doi = self._doi(item)
        language = self._language(item)
        is_open_access = self._open_access(item)
        citation_count = self._citation_count(item)
        url = self._url(item)
        abstract = self._abstract(item)
        score = self._score(item)
        return SearchHit(
            provider_key=self._provider_key,
            provider_identifier=identifier,
            title=title,
            abstract=abstract,
            authors=authors,
            year=year,
            venue=venue,
            doi=doi,
            language=language,
            is_open_access=is_open_access,
            citation_count=citation_count,
            url=url,
            score=score,
            extra={"type": item.get("type", "")},
        )

    def _identifier(self, item: dict[str, Any]) -> str:
        doi = item.get("DOI")
        if isinstance(doi, str) and doi:
            return doi.lower()
        url = item.get("URL")
        if isinstance(url, str) and url:
            return url
        return ""

    def _first_title(self, item: dict[str, Any]) -> str:
        titles = item.get("title")
        if isinstance(titles, list) and titles:
            first = titles[0]
            if isinstance(first, str):
                return _normalize_whitespace(first)
        return ""

    def _authors(self, item: dict[str, Any]) -> tuple[str, ...]:
        authors_raw = item.get("author")
        if not isinstance(authors_raw, list):
            return ()
        results: list[str] = []
        for author in authors_raw:
            if not isinstance(author, dict):
                continue
            given = author.get("given")
            family = author.get("family")
            if isinstance(given, str) and isinstance(family, str):
                results.append(f"{given} {family}".strip())
            elif isinstance(family, str):
                results.append(family.strip())
            elif isinstance(given, str):
                results.append(given.strip())
            elif isinstance(author.get("name"), str):
                results.append(str(author["name"]).strip())
        return tuple(results)

    def _year(self, item: dict[str, Any]) -> int | None:
        for key in (
            "published-print",
            "published-online",
            "issued",
            "created",
            "deposited",
            "indexed",
        ):
            block = item.get(key)
            if not isinstance(block, dict):
                continue
            parts = block.get("date-parts")
            if not isinstance(parts, list) or not parts:
                continue
            first = parts[0]
            if not isinstance(first, list) or not first:
                continue
            year = first[0]
            if isinstance(year, int):
                return year
        return None

    def _first_container_title(self, item: dict[str, Any]) -> str:
        containers = item.get("container-title")
        if isinstance(containers, list) and containers:
            first = containers[0]
            if isinstance(first, str):
                return _normalize_whitespace(first)
        return ""

    def _doi(self, item: dict[str, Any]) -> str | None:
        doi = item.get("DOI")
        if isinstance(doi, str) and doi:
            return doi.lower()
        return None

    def _language(self, item: dict[str, Any]) -> str | None:
        language = item.get("language")
        if isinstance(language, str) and language:
            return language.lower()
        return None

    def _open_access(self, item: dict[str, Any]) -> bool:
        for license_entry in item.get("license", []) or []:
            if not isinstance(license_entry, dict):
                continue
            url = license_entry.get("URL")
            if isinstance(url, str) and "creativecommons.org" in url:
                return True
        return False

    def _citation_count(self, item: dict[str, Any]) -> int | None:
        count = item.get("is-referenced-by-count")
        if isinstance(count, int):
            return count
        return None

    def _url(self, item: dict[str, Any]) -> str | None:
        url = item.get("URL")
        if isinstance(url, str) and url:
            return url
        return None

    def _abstract(self, item: dict[str, Any]) -> str:
        abstract = item.get("abstract")
        if not isinstance(abstract, str) or not abstract:
            return ""
        # Crossref returns JATS XML. Strip tags and decode entities to
        # obtain plain text. This is lossy: structural markup (paragraphs,
        # emphasis) is discarded.
        stripped = _JATS_TAG_PATTERN.sub(" ", abstract)
        decoded = html.unescape(stripped)
        return _normalize_whitespace(decoded)

    def _score(self, item: dict[str, Any]) -> float | None:
        score = item.get("score")
        if isinstance(score, (int, float)):
            return float(score)
        return None


def _normalize_whitespace(value: str) -> str:
    return _WHITESPACE_PATTERN.sub(" ", value).strip()