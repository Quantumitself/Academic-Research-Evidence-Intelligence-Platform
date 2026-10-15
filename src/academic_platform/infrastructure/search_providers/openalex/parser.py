"""Parsing of OpenAlex responses into provider-neutral hits.

OpenAlex returns works in a JSON object with a ``results`` array and a
``meta`` object carrying ``count`` and ``next_cursor``. Each work carries
an ``id`` (the OpenAlex URL), a ``doi`` (a URL), a ``title``, an
``abstract_inverted_index`` (a mapping from token to positions), a
``publication_year``, a ``host_venue`` object or a ``primary_location``
object, an ``authorships`` array, an ``open_access`` object, and a
``cited_by_count``.

Design decisions
----------------
- The parser never raises on a missing optional field. It substitutes a
  neutral value and continues.
- The parser raises ``ProviderResponseError`` only when the top-level
  structure is not what OpenAlex documents.
- The inverted abstract index is reconstructed into plain text. OpenAlex
  does not return abstracts as plain text; the index maps each token to
  the positions it occupies in the abstract. The parser reconstructs the
  text by placing tokens at their positions.
- The DOI returned by OpenAlex is a URL. The parser extracts the bare
  DOI and normalizes it to lowercase.
- The work identifier is the OpenAlex identifier extracted from the
  work's ``id`` URL.
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


class OpenAlexResponseParser:
    """Parse OpenAlex response payloads into provider-neutral hits."""

    def __init__(self, provider_key: str = "openalex") -> None:
        self._provider_key = provider_key

    @property
    def provider_key(self) -> str:
        return self._provider_key

    def parse(
        self,
        payload: dict[str, Any],
    ) -> tuple[list[SearchHit], int | None, str | None]:
        """Parse an OpenAlex response.

        Returns
        -------
        tuple[list[SearchHit], int | None, str | None]
            The parsed hits, the total number of matching works reported
            by OpenAlex (``meta.count``), and the next cursor
            (``meta.next_cursor``).
        """
        if not isinstance(payload, dict):
            raise ProviderResponseError("OpenAlex response is not a JSON object")
        results = payload.get("results")
        if not isinstance(results, list):
            raise ProviderResponseError(
                "OpenAlex response is missing the 'results' list"
            )
        meta = payload.get("meta") or {}
        total_value = meta.get("count") if isinstance(meta, dict) else None
        total = int(total_value) if isinstance(total_value, int) else None
        next_cursor_value = (
            meta.get("next_cursor") if isinstance(meta, dict) else None
        )
        next_cursor = (
            str(next_cursor_value)
            if isinstance(next_cursor_value, str) and next_cursor_value
            else None
        )

        hits: list[SearchHit] = []
        for index, item in enumerate(results):
            try:
                hit = self._parse_item(item)
            except Exception as exc:  # noqa: BLE001 - boundary
                _logger.warning(
                    "Skipping malformed OpenAlex item at index %d: %s",
                    index,
                    exc,
                )
                continue
            if hit is not None:
                hits.append(hit)
        return hits, total, next_cursor

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
            extra={"type": item.get("type", "")},
        )

    def _identifier(self, item: dict[str, Any]) -> str:
        raw = item.get("id")
        if isinstance(raw, str) and raw:
            # OpenAlex identifiers are URLs such as
            # https://openalex.org/W1234567890. Extract the identifier.
            return raw.rsplit("/", 1)[-1]
        return ""

    def _title(self, item: dict[str, Any]) -> str:
        title = item.get("title")
        if isinstance(title, str) and title:
            return _normalize_whitespace(title)
        display_name = item.get("display_name")
        if isinstance(display_name, str) and display_name:
            return _normalize_whitespace(display_name)
        return ""

    def _abstract(self, item: dict[str, Any]) -> str:
        index = item.get("abstract_inverted_index")
        if not isinstance(index, dict):
            return ""
        positions: dict[int, str] = {}
        for token, offsets in index.items():
            if not isinstance(token, str):
                continue
            if not isinstance(offsets, list):
                continue
            for offset in offsets:
                if isinstance(offset, int) and offset >= 0:
                    positions[offset] = token
        if not positions:
            return ""
        max_position = max(positions.keys())
        words = [positions.get(index, "") for index in range(max_position + 1)]
        joined = " ".join(word for word in words if word)
        return _normalize_whitespace(joined)

    def _authors(self, item: dict[str, Any]) -> tuple[str, ...]:
        authorships = item.get("authorships")
        if not isinstance(authorships, list):
            return ()
        results: list[str] = []
        for authorship in authorships:
            if not isinstance(authorship, dict):
                continue
            author = authorship.get("author")
            if not isinstance(author, dict):
                continue
            display_name = author.get("display_name")
            if isinstance(display_name, str) and display_name:
                results.append(_normalize_whitespace(display_name))
        return tuple(results)

    def _year(self, item: dict[str, Any]) -> int | None:
        year = item.get("publication_year")
        if isinstance(year, int):
            return year
        return None

    def _venue(self, item: dict[str, Any]) -> str:
        # OpenAlex exposes venue information through two objects:
        # ``primary_location.source`` (the current representation) and
        # ``host_venue`` (the older representation). The parser prefers
        # the current representation and falls back to the older one.
        primary = item.get("primary_location")
        if isinstance(primary, dict):
            source = primary.get("source")
            if isinstance(source, dict):
                display_name = source.get("display_name")
                if isinstance(display_name, str) and display_name:
                    return _normalize_whitespace(display_name)
        host = item.get("host_venue")
        if isinstance(host, dict):
            display_name = host.get("display_name")
            if isinstance(display_name, str) and display_name:
                return _normalize_whitespace(display_name)
        return ""

    def _doi(self, item: dict[str, Any]) -> str | None:
        raw = item.get("doi")
        if not isinstance(raw, str) or not raw:
            return None
        # OpenAlex returns the DOI as a URL. Extract the bare DOI.
        stripped = raw
        if stripped.startswith("https://doi.org/"):
            stripped = stripped[len("https://doi.org/"):]
        elif stripped.startswith("http://doi.org/"):
            stripped = stripped[len("http://doi.org/"):]
        stripped = stripped.strip().lower()
        return stripped or None

    def _language(self, item: dict[str, Any]) -> str | None:
        language = item.get("language")
        if isinstance(language, str) and language:
            return language.lower()
        return None

    def _open_access(self, item: dict[str, Any]) -> bool:
        open_access = item.get("open_access")
        if isinstance(open_access, dict):
            return bool(open_access.get("is_oa"))
        return False

    def _citation_count(self, item: dict[str, Any]) -> int | None:
        count = item.get("cited_by_count")
        if isinstance(count, int):
            return count
        return None

    def _url(self, item: dict[str, Any]) -> str | None:
        # OpenAlex returns the work URL through ``id``. A DOI URL is also
        # provided when the work has a DOI. The parser prefers the DOI
        # URL when present and falls back to the OpenAlex URL.
        raw_doi = item.get("doi")
        if isinstance(raw_doi, str) and raw_doi:
            return raw_doi
        raw_id = item.get("id")
        if isinstance(raw_id, str) and raw_id:
            return raw_id
        return None

    def _score(self, item: dict[str, Any]) -> float | None:
        score = item.get("relevance_score")
        if isinstance(score, (int, float)):
            return float(score)
        return None


def _normalize_whitespace(value: str) -> str:
    return _WHITESPACE_PATTERN.sub(" ", value).strip()