"""Parsing of PubMed responses into provider-neutral hits.

The parser consumes the JSON payloads returned by ``esearch``,
``esummary``, and ``efetch``. Each payload has a distinct shape:

- esearch: ``esearchresult`` object containing ``idlist`` (a list of
  identifiers) and ``count`` (the total number of matching records).
- esummary: ``result`` object whose keys are identifiers and whose
  values are metadata objects (with a ``uids`` entry listing the order).
  An ``error`` key is present when the provider reports a problem.
- efetch: ``PubmedArticleSet`` object containing ``PubmedArticle``
  entries, each with ``MedlineCitation`` and ``Article`` structures. In
  practice, the JSON representation of efetch uses the same
  ``result``-based shape as esummary on the JSON endpoints used here.

The parser exposes three entry points, one per response shape. Each
entry point returns the data the adapter needs; the adapter composes them
into a ``SearchResponse``.

Design decisions
----------------
- The parser never raises on a missing optional field. It substitutes a
  neutral value and continues.
- The parser raises ``ProviderResponseError`` only when the top-level
  structure is not what PubMed documents.
- Individual malformed entries are skipped with a warning. A single bad
  entry never invalidates a response.
- The parser consumes the JSON ``esummary`` representation for
  bibliographic metadata. When the ``efetch`` response carries
  abstracts, the parser merges them into the summary entries by
  identifier. When the ``efetch`` response does not carry abstracts, the
  parser leaves the abstract empty rather than fabricating it.
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
_MEDLINE_TAG_PATTERN = re.compile(r"<[^>]+>")


class PubMedResponseParser:
    """Parse PubMed response payloads into provider-neutral hits."""

    def __init__(self, provider_key: str = "pubmed") -> None:
        self._provider_key = provider_key

    @property
    def provider_key(self) -> str:
        return self._provider_key

    # ------------------------------------------------------------------
    # esearch
    # ------------------------------------------------------------------
    def parse_search(self, payload: dict[str, Any]) -> tuple[list[str], int | None]:
        """Parse an esearch response.

        Returns
        -------
        tuple[list[str], int | None]
            The list of identifiers in the order PubMed returned them,
            and the total number of matching records.
        """
        if not isinstance(payload, dict):
            raise ProviderResponseError("PubMed esearch response is not a JSON object")
        result = payload.get("esearchresult")
        if not isinstance(result, dict):
            raise ProviderResponseError(
                "PubMed esearch response is missing 'esearchresult'"
            )
        id_list = result.get("idlist")
        if not isinstance(id_list, list):
            raise ProviderResponseError(
                "PubMed esearch response is missing 'idlist'"
            )
        identifiers: list[str] = []
        for entry in id_list:
            if isinstance(entry, str) and entry:
                identifiers.append(entry)
        count_raw = result.get("count")
        total = int(count_raw) if isinstance(count_raw, (int, str)) and str(count_raw).isdigit() else None
        return identifiers, total

    # ------------------------------------------------------------------
    # esummary
    # ------------------------------------------------------------------
    def parse_summary(
        self,
        payload: dict[str, Any],
        ordered_identifiers: list[str],
    ) -> list[SearchHit]:
        """Parse an esummary response in the order of ``ordered_identifiers``."""
        if not isinstance(payload, dict):
            raise ProviderResponseError("PubMed esummary response is not a JSON object")
        result = payload.get("result")
        if not isinstance(result, dict):
            raise ProviderResponseError(
                "PubMed esummary response is missing 'result'"
            )
        if "error" in result:
            raise ProviderResponseError(
                f"PubMed esummary reported an error: {result['error']}"
            )
        hits: list[SearchHit] = []
        for identifier in ordered_identifiers:
            entry = result.get(identifier)
            if not isinstance(entry, dict):
                _logger.warning(
                    "PubMed esummary did not return an entry for identifier %s",
                    identifier,
                )
                continue
            try:
                hit = self._parse_summary_entry(identifier, entry)
            except Exception as exc:  # noqa: BLE001 - boundary
                _logger.warning(
                    "Skipping malformed PubMed summary entry %s: %s",
                    identifier,
                    exc,
                )
                continue
            if hit is not None:
                hits.append(hit)
        return hits

    def _parse_summary_entry(
        self,
        identifier: str,
        entry: dict[str, Any],
    ) -> SearchHit | None:
        title = entry.get("title") or ""
        if not isinstance(title, str):
            title = ""
        authors = self._summary_authors(entry)
        year = self._summary_year(entry)
        venue = entry.get("fulljournalname") or entry.get("source") or ""
        if not isinstance(venue, str):
            venue = ""
        doi = self._summary_doi(entry)
        language = self._summary_language(entry)
        url = f"https://pubmed.ncbi.nlm.nih.gov/{identifier}/"
        return SearchHit(
            provider_key=self._provider_key,
            provider_identifier=identifier,
            title=_normalize_whitespace(title),
            abstract="",
            authors=authors,
            year=year,
            venue=_normalize_whitespace(venue) if isinstance(venue, str) else "",
            doi=doi,
            language=language,
            is_open_access=False,
            citation_count=None,
            url=url,
            score=None,
            extra={"pmid": identifier, "type": entry.get("pubtype", [])},
        )

    def _summary_authors(self, entry: dict[str, Any]) -> tuple[str, ...]:
        authors = entry.get("authors")
        if not isinstance(authors, list):
            return ()
        results: list[str] = []
        for author in authors:
            if not isinstance(author, dict):
                continue
            name = author.get("name")
            if isinstance(name, str) and name:
                results.append(_normalize_whitespace(name))
        return tuple(results)

    def _summary_year(self, entry: dict[str, Any]) -> int | None:
        pubdate = entry.get("pubdate")
        if isinstance(pubdate, str) and pubdate:
            first = pubdate.split(" ", 1)[0]
            if first.isdigit() and len(first) == 4:
                return int(first)
        # Fall back to the "epubdate" or "sortpubdate" fields.
        for key in ("epubdate", "sortpubdate"):
            value = entry.get(key)
            if isinstance(value, str) and len(value) >= 4:
                candidate = value[:4]
                if candidate.isdigit():
                    return int(candidate)
        return None

    def _summary_doi(self, entry: dict[str, Any]) -> str | None:
        ids = entry.get("articleids")
        if not isinstance(ids, list):
            return None
        for identifier in ids:
            if not isinstance(identifier, dict):
                continue
            id_type = identifier.get("idtype")
            value = identifier.get("value")
            if id_type == "doi" and isinstance(value, str) and value:
                return value.strip().lower()
        return None

    def _summary_language(self, entry: dict[str, Any]) -> str | None:
        language = entry.get("lang")
        if isinstance(language, list) and language:
            first = language[0]
            if isinstance(first, str) and first:
                return first.lower()
        if isinstance(language, str) and language:
            return language.lower()
        return None

    # ------------------------------------------------------------------
    # efetch abstracts
    # ------------------------------------------------------------------
    def parse_abstracts(
        self,
        payload: dict[str, Any],
    ) -> dict[str, str]:
        """Parse an efetch response into a mapping of identifier to abstract.

        Returns
        -------
        dict[str, str]
            A mapping from PubMed identifier to plain-text abstract. The
            mapping omits identifiers whose abstract is empty.
        """
        if not isinstance(payload, dict):
            raise ProviderResponseError("PubMed efetch response is not a JSON object")
        result = payload.get("result")
        if not isinstance(result, dict):
            raise ProviderResponseError(
                "PubMed efetch response is missing 'result'"
            )
        abstracts: dict[str, str] = {}
        for key, value in result.items():
            if key in {"uids", "error"}:
                continue
            if not isinstance(value, dict):
                continue
            abstract = self._extract_abstract(value)
            if abstract:
                abstracts[key] = abstract
        return abstracts

    def _extract_abstract(self, entry: dict[str, Any]) -> str:
        # The JSON representation of efetch varies. Two shapes are
        # observed: a top-level "abstract" string, and a nested
        # "abstracttext" array whose entries carry "text" fields.
        abstract = entry.get("abstract")
        if isinstance(abstract, str) and abstract:
            return _strip_markup(abstract)
        abstract_text = entry.get("abstracttext")
        if isinstance(abstract_text, str) and abstract_text:
            return _strip_markup(abstract_text)
        if isinstance(abstract_text, list):
            parts: list[str] = []
            for part in abstract_text:
                if isinstance(part, str):
                    parts.append(part)
                elif isinstance(part, dict):
                    label = part.get("label")
                    text = part.get("text")
                    if isinstance(text, str) and text:
                        if isinstance(label, str) and label:
                            parts.append(f"{label}: {text}")
                        else:
                            parts.append(text)
            if parts:
                return _normalize_whitespace(_strip_markup(" ".join(parts)))
        return ""

    # ------------------------------------------------------------------
    # Composition helper
    # ------------------------------------------------------------------
    def merge_abstracts(
        self,
        hits: list[SearchHit],
        abstracts: dict[str, str],
    ) -> list[SearchHit]:
        """Return hits with abstracts filled in from the efetch mapping."""
        if not abstracts:
            return hits
        merged: list[SearchHit] = []
        for hit in hits:
            abstract = abstracts.get(hit.provider_identifier, "")
            if not abstract:
                merged.append(hit)
                continue
            merged.append(
                SearchHit(
                    provider_key=hit.provider_key,
                    provider_identifier=hit.provider_identifier,
                    title=hit.title,
                    abstract=abstract,
                    authors=hit.authors,
                    year=hit.year,
                    venue=hit.venue,
                    doi=hit.doi,
                    language=hit.language,
                    is_open_access=hit.is_open_access,
                    citation_count=hit.citation_count,
                    url=hit.url,
                    score=hit.score,
                    extra=dict(hit.extra),
                )
            )
        return merged


def _normalize_whitespace(value: str) -> str:
    return _WHITESPACE_PATTERN.sub(" ", value).strip()


def _strip_markup(value: str) -> str:
    stripped = _MEDLINE_TAG_PATTERN.sub(" ", value)
    return _normalize_whitespace(stripped)