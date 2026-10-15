"""Parsing of Europe PMC responses into provider-neutral hits.

Europe PMC returns papers in a JSON object with a ``resultList`` object
carrying a ``result`` array and a ``hitCount`` total. The response also
carries a ``nextCursorMark`` for cursor-based pagination.

Design decisions
----------------
- The parser never raises on a missing optional field. It substitutes a
  neutral value and continues.
- Individual malformed items are skipped with a warning. The parser
  raises ``ProviderResponseError`` only when the top-level structure is
  not what Europe PMC documents.
- The DOI is extracted from the ``doi`` field when present. Europe PMC
  also returns ``pmid``, ``pmcid``, and ``id`` fields; the adapter uses
  ``id`` as the provider identifier when a DOI is absent.
- The abstract is returned as plain text when ``resultType=core`` is
  requested. The parser strips any residual markup.
- The open-access flag is derived from the ``isOpenAccess`` field.
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
_MARKUP_PATTERN = re.compile(r"<[^>]+>")


class EuropePmcResponseParser:
    """Parse Europe PMC response payloads into provider-neutral hits."""

    def __init__(self, provider_key: str = "europe_pmc") -> None:
        self._provider_key = provider_key

    @property
    def provider_key(self) -> str:
        return self._provider_key

    def parse(
        self,
        payload: dict[str, Any],
    ) -> tuple[list[SearchHit], int | None, str | None]:
        """Parse a Europe PMC response.

        Returns
        -------
        tuple[list[SearchHit], int | None, str | None]
            The parsed hits, the total number of matching records
            (``hitCount``), and the next cursor mark
            (``nextCursorMark``).
        """
        if not isinstance(payload, dict):
            raise ProviderResponseError(
                "Europe PMC response is not a JSON object"
            )
        result_list = payload.get("resultList")
        if not isinstance(result_list, dict):
            raise ProviderResponseError(
                "Europe PMC response is missing 'resultList'"
            )
        results = result_list.get("result")
        if not isinstance(results, list):
            raise ProviderResponseError(
                "Europe PMC response is missing 'resultList.result'"
            )
        hit_count_raw = payload.get("hitCount")
        total = (
            int(hit_count_raw)
            if isinstance(hit_count_raw, (int, str)) and str(hit_count_raw).isdigit()
            else None
        )
        next_cursor_raw = payload.get("nextCursorMark")
        next_cursor = (
            str(next_cursor_raw)
            if isinstance(next_cursor_raw, str) and next_cursor_raw
            else None
        )

        hits: list[SearchHit] = []
        for index, item in enumerate(results):
            try:
                hit = self._parse_item(item)
            except Exception as exc:  # noqa: BLE001 - boundary
                _logger.warning(
                    "Skipping malformed Europe PMC item at index %d: %s",
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
            score=None,
            extra={
                "pmid": item.get("pmid"),
                "pmcid": item.get("pmcid"),
                "source": item.get("source"),
            },
        )

    def _identifier(self, item: dict[str, Any]) -> str:
        for key in ("id", "pmid", "pmcid"):
            value = item.get(key)
            if isinstance(value, str) and value:
                return value
        return ""

    def _title(self, item: dict[str, Any]) -> str:
        title = item.get("title")
        if isinstance(title, str) and title:
            return _normalize_whitespace(_strip_markup(title))
        return ""

    def _abstract(self, item: dict[str, Any]) -> str:
        abstract = item.get("abstractText")
        if isinstance(abstract, str) and abstract:
            return _normalize_whitespace(_strip_markup(abstract))
        return ""

    def _authors(self, item: dict[str, Any]) -> tuple[str, ...]:
        author_string = item.get("authorString")
        if isinstance(author_string, str) and author_string:
            raw_authors = author_string.split(",")
            results: list[str] = []
            for raw in raw_authors:
                name = _normalize_whitespace(raw.strip().rstrip("."))
                if name and name != "et al":
                    results.append(name)
            if results:
                return tuple(results)
        author_list = item.get("authorList")
        if isinstance(author_list, dict):
            authors = author_list.get("author")
            if isinstance(authors, list):
                collected: list[str] = []
                for author in authors:
                    if not isinstance(author, dict):
                        continue
                    name = (
                        author.get("fullName")
                        or author.get("collectiveName")
                        or ""
                    )
                    if isinstance(name, str) and name:
                        collected.append(_normalize_whitespace(name))
                if collected:
                    return tuple(collected)
        return ()

    def _year(self, item: dict[str, Any]) -> int | None:
        year = item.get("pubYear")
        if isinstance(year, int):
            return year
        if isinstance(year, str) and year.isdigit():
            return int(year)
        return None

    def _venue(self, item: dict[str, Any]) -> str:
        journal = item.get("journalInfo")
        if isinstance(journal, dict):
            journal_obj = journal.get("journal")
            if isinstance(journal_obj, dict):
                title = journal_obj.get("title")
                if isinstance(title, str) and title:
                    return _normalize_whitespace(title)
        venue = item.get("journalTitle")
        if isinstance(venue, str) and venue:
            return _normalize_whitespace(venue)
        return ""

    def _doi(self, item: dict[str, Any]) -> str | None:
        doi = item.get("doi")
        if isinstance(doi, str) and doi:
            return doi.strip().lower()
        return None

    def _language(self, item: dict[str, Any]) -> str | None:
        language = item.get("language")
        if isinstance(language, str) and language:
            return language.lower()
        return None

    def _open_access(self, item: dict[str, Any]) -> bool:
        value = item.get("isOpenAccess")
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in {"y", "yes", "true"}
        return False

    def _citation_count(self, item: dict[str, Any]) -> int | None:
        count = item.get("citedByCount")
        if isinstance(count, int):
            return count
        if isinstance(count, str) and count.isdigit():
            return int(count)
        return None

    def _url(self, item: dict[str, Any]) -> str | None:
        doi = item.get("doi")
        if isinstance(doi, str) and doi:
            return f"https://doi.org/{doi.strip().lower()}"
        identifier = self._identifier(item)
        if identifier:
            return f"https://europepmc.org/article/MED/{identifier}"
        return None


def _normalize_whitespace(value: str) -> str:
    return _WHITESPACE_PATTERN.sub(" ", value).strip()


def _strip_markup(value: str) -> str:
    return _MARKUP_PATTERN.sub(" ", value)