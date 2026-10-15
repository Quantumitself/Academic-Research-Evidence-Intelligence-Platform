"""Parsing of Semantic Scholar responses into provider-neutral hits.

Semantic Scholar returns papers in a JSON object with a ``data`` array
and a ``total`` count. Each paper carries a ``paperId``, an
``externalIds`` object (with a ``DOI`` when available), a ``title``, an
``abstract``, a ``year``, a ``venue``, an ``authors`` array, an
``openAccessPdf`` object, and a ``citationCount``.

Design decisions
----------------
- The parser never raises on a missing optional field. It substitutes a
  neutral value and continues.
- Individual malformed items are skipped with a warning. The parser
  raises ``ProviderResponseError`` only when the top-level structure is
  not what Semantic Scholar documents.
- The DOI is extracted from ``externalIds`` when present. Papers without
  a DOI still produce a hit; their identifier is the ``paperId``.
- The paper identifier is the ``paperId`` returned by Semantic Scholar.
- The open-access flag is derived from the presence of an
  ``openAccessPdf`` object with a non-empty ``url``.
"""

from __future__ import annotations

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

_WHITESPACE_PATTERN = re.compile(r"\s+")


class SemanticScholarResponseParser:
    """Parse Semantic Scholar response payloads into provider-neutral hits."""

    def __init__(self, provider_key: str = "semantic_scholar") -> None:
        self._provider_key = provider_key

    @property
    def provider_key(self) -> str:
        return self._provider_key

    def parse(
        self,
        payload: dict[str, Any],
    ) -> tuple[list[SearchHit], int | None, str | None]:
        """Parse a Semantic Scholar response.

        Returns
        -------
        tuple[list[SearchHit], int | None, str | None]
            The parsed hits, the total number of matching works reported
            by Semantic Scholar (``total``), and the next cursor. The
            relevance-search endpoint does not use cursor pagination, so
            the cursor is always ``None``.
        """
        if not isinstance(payload, dict):
            raise ProviderResponseError(
                "Semantic Scholar response is not a JSON object"
            )
        data = payload.get("data")
        if not isinstance(data, list):
            raise ProviderResponseError(
                "Semantic Scholar response is missing the 'data' list"
            )
        total_raw = payload.get("total")
        total = int(total_raw) if isinstance(total_raw, int) else None

        hits: list[SearchHit] = []
        for index, item in enumerate(data):
            try:
                hit = self._parse_item(item)
            except Exception as exc:  # noqa: BLE001 - boundary
                _logger.warning(
                    "Skipping malformed Semantic Scholar item at index %d: %s",
                    index,
                    exc,
                )
                continue
            if hit is not None:
                hits.append(hit)
        return hits, total, None

    # ------------------------------------------------------------------
    # Item parsing
    # ------------------------------------------------------------------
    def _parse_item(self, item: Any) -> SearchHit | None:
        if not isinstance(item, dict):
            return None
        identifier = self._identifier(item)
        if not identifier:
            return None
        return SearchHit(
            provider_key=self._provider_key,
            provider_identifier=identifier,
            title=self._title(item),
            abstract=self._abstract(item),
            authors=self._authors(item),
            year=self._year(item),
            venue=self._venue(item),
            doi=self._doi(item),
            language=self._language(item),
            is_open_access=self._open_access(item),
            citation_count=self._citation_count(item),
            url=self._url(item),
            score=self._score(item),
            extra={"paper_id": identifier},
        )

    def _identifier(self, item: dict[str, Any]) -> str:
        raw = item.get("paperId")
        if isinstance(raw, str) and raw:
            return raw
        return ""

    def _title(self, item: dict[str, Any]) -> str:
        title = item.get("title")
        if isinstance(title, str) and title:
            return _normalize_whitespace(title)
        return ""

    def _abstract(self, item: dict[str, Any]) -> str:
        abstract = item.get("abstract")
        if isinstance(abstract, str) and abstract:
            return _normalize_whitespace(abstract)
        return ""

    def _authors(self, item: dict[str, Any]) -> tuple[str, ...]:
        authors_raw = item.get("authors")
        if not isinstance(authors_raw, list):
            return ()
        results: list[str] = []
        for author in authors_raw:
            if not isinstance(author, dict):
                continue
            name = author.get("name")
            if isinstance(name, str) and name:
                results.append(_normalize_whitespace(name))
        return tuple(results)

    def _year(self, item: dict[str, Any]) -> int | None:
        year = item.get("year")
        if isinstance(year, int):
            return year
        return None

    def _venue(self, item: dict[str, Any]) -> str:
        venue = item.get("venue")
        if isinstance(venue, str) and venue:
            return _normalize_whitespace(venue)
        return ""

    def _doi(self, item: dict[str, Any]) -> str | None:
        external_ids = item.get("externalIds")
        if not isinstance(external_ids, dict):
            return None
        doi = external_ids.get("DOI")
        if isinstance(doi, str) and doi:
            return doi.strip().lower()
        return None

    def _language(self, item: dict[str, Any]) -> str | None:
        language = item.get("language")
        if isinstance(language, str) and language:
            return language.lower()
        return None

    def _open_access(self, item: dict[str, Any]) -> bool:
        open_access = item.get("openAccessPdf")
        if isinstance(open_access, dict):
            url = open_access.get("url")
            if isinstance(url, str) and url:
                return True
        return False

    def _citation_count(self, item: dict[str, Any]) -> int | None:
        count = item.get("citationCount")
        if isinstance(count, int):
            return count
        return None

    def _url(self, item: dict[str, Any]) -> str | None:
        external_ids = item.get("externalIds")
        if isinstance(external_ids, dict):
            doi = external_ids.get("DOI")
            if isinstance(doi, str) and doi:
                return f"https://doi.org/{doi.lower()}"
        paper_id = item.get("paperId")
        if isinstance(paper_id, str) and paper_id:
            return f"https://www.semanticscholar.org/paper/{paper_id}"
        return None

    def _score(self, item: dict[str, Any]) -> float | None:
        score = item.get("score")
        if isinstance(score, (int, float)):
            return float(score)
        return None


def _normalize_whitespace(value: str) -> str:
    return _WHITESPACE_PATTERN.sub(" ", value).strip()