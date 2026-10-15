"""Application service for in-document search.

The service searches a single document's persisted chunks for a query.
The search is literal by default: the query is matched as a substring,
case-insensitively. A regular-expression mode is available when the
caller explicitly requests it.

Design decisions
----------------
- The service reads from the ``document_chunk`` table through the
  repository layer. It never reads the PDF file.
- The service is literal by default. Substring matching is
  deterministic and easy for the user to predict; regular expressions
  are opt-in.
- The service returns every match up to the configured limit. It marks
  the result as truncated when the limit is reached.
- Snippets are produced with a configurable radius. Matched terms are
  wrapped in the service's marker strings so the presentation layer can
  apply highlight styling without re-searching the snippet.
- The service never modifies the database.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from academic_platform.application.document_search.errors import (
    DocumentSearchError,
    DocumentSearchNotFoundError,
)
from academic_platform.application.document_search.model import (
    DocumentSearchMatch,
    DocumentSearchResult,
)
from academic_platform.infrastructure.repositories.errors import (
    RepositoryError,
)
from academic_platform.infrastructure.repositories.manager import (
    RepositoryManager,
)

_logger = logging.getLogger(__name__)

_DEFAULT_LIMIT = 500
_SNIPPET_RADIUS = 40
_MATCH_START_MARKER = "[["
_MATCH_END_MARKER = "]]"


@dataclass(frozen=True, slots=True)
class _MatchRange:
    start: int
    end: int


class DocumentSearchService:
    """Search a single document's stored chunks."""

    def __init__(
        self,
        repositories: RepositoryManager,
        *,
        default_limit: int = _DEFAULT_LIMIT,
        snippet_radius: int = _SNIPPET_RADIUS,
    ) -> None:
        if default_limit < 1:
            raise ValueError("default_limit must be at least 1")
        if snippet_radius < 1:
            raise ValueError("snippet_radius must be at least 1")
        self._repositories = repositories
        self._default_limit = default_limit
        self._snippet_radius = snippet_radius

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def search(
        self,
        document_key: str,
        query: str,
        *,
        case_sensitive: bool = False,
        use_regex: bool = False,
        limit: int | None = None,
    ) -> DocumentSearchResult:
        """Search a document for a query.

        Parameters
        ----------
        document_key:
            The document to search.
        query:
            The search text. Empty queries return an empty result.
        case_sensitive:
            When True, matching is case-sensitive.
        use_regex:
            When True, the query is interpreted as a regular expression.
        limit:
            Maximum number of matches to return. Defaults to the
            service's configured limit.
        """
        if not query:
            return DocumentSearchResult(document_key=document_key, query=query)
        document = self._require_document(document_key)
        chunks = self._load_chunks(document.id)
        effective_limit = max(1, int(limit)) if limit is not None else self._default_limit
        pattern = _compile_pattern(query, case_sensitive=case_sensitive, use_regex=use_regex)

        matches: list[DocumentSearchMatch] = []
        truncated = False
        for chunk in chunks:
            content = chunk.content or ""
            if not content:
                continue
            for match_range in _iter_matches(pattern, content):
                if len(matches) >= effective_limit:
                    truncated = True
                    break
                snippet = _build_snippet(
                    content,
                    match_range,
                    radius=self._snippet_radius,
                    start_marker=_MATCH_START_MARKER,
                    end_marker=_MATCH_END_MARKER,
                )
                matches.append(
                    DocumentSearchMatch(
                        document_key=document_key,
                        page_number=chunk.page_number,
                        chunk_index=chunk.chunk_index,
                        start_offset=match_range.start,
                        end_offset=match_range.end,
                        snippet=snippet,
                        match_text=content[match_range.start:match_range.end],
                    )
                )
            if truncated:
                break

        return DocumentSearchResult(
            document_key=document_key,
            query=query,
            matches=tuple(matches),
            truncated=truncated,
            message=(
                "The match limit was reached. Additional matches are not shown."
                if truncated
                else ""
            ),
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _require_document(self, document_key: str):
        repo = self._repositories.get("document_asset")
        try:
            row = repo.find_by_key(document_key)
        except RepositoryError as exc:
            raise DocumentSearchError(
                f"Unable to read document {document_key!r}: {exc}"
            ) from exc
        if row is None:
            raise DocumentSearchNotFoundError(
                f"No document with key {document_key!r}"
            )
        return row

    def _load_chunks(self, document_id: int):
        repo = self._repositories.get("document_chunk")
        try:
            return repo.list_for_document(document_id)
        except RepositoryError as exc:
            raise DocumentSearchError(
                f"Unable to read document chunks: {exc}"
            ) from exc


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
def _compile_pattern(
    query: str,
    *,
    case_sensitive: bool,
    use_regex: bool,
) -> re.Pattern[str]:
    flags = 0 if case_sensitive else re.IGNORECASE
    if use_regex:
        try:
            return re.compile(query, flags)
        except re.error as exc:
            raise DocumentSearchError(
                f"Invalid regular expression: {exc}"
            ) from exc
    return re.compile(re.escape(query), flags)


def _iter_matches(pattern: re.Pattern[str], content: str):
    for match in pattern.finditer(content):
        yield _MatchRange(start=match.start(), end=match.end())


def _build_snippet(
    content: str,
    match_range: _MatchRange,
    *,
    radius: int,
    start_marker: str,
    end_marker: str,
) -> str:
    start = max(0, match_range.start - radius)
    end = min(len(content), match_range.end + radius)
    prefix = "…" if start > 0 else ""
    suffix = "…" if end < len(content) else ""
    before = content[start:match_range.start]
    matched = content[match_range.start:match_range.end]
    after = content[match_range.end:end]
    # Collapse newlines so the snippet renders on a single line.
    before = _collapse_whitespace(before)
    matched = _collapse_whitespace(matched)
    after = _collapse_whitespace(after)
    return f"{prefix}{before}{start_marker}{matched}{end_marker}{after}{suffix}"


_WHITESPACE_RUN = re.compile(r"\s+")


def _collapse_whitespace(value: str) -> str:
    return _WHITESPACE_RUN.sub(" ", value)