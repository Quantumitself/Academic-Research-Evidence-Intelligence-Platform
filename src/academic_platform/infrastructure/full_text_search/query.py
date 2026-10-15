"""FTS5 query service.

The service executes MATCH queries against the FTS5 tables, returns
ranked hits, and produces snippets with highlighting markers around the
matched terms.

Design decisions
----------------
- FTS5's ``snippet`` function produces a highlighted fragment for a
  named column. The service uses it to produce a bounded snippet per
  hit; the snippet is the same column the query matched.
- FTS5's ``rank`` function returns a numeric relevance score. Lower
  values mean better matches; the service sorts ascending by rank.
- The service never rewrites the query. It passes the MATCH expression
  to FTS5 unchanged. Callers are responsible for producing a valid FTS5
  query string; the service validates the query only for emptiness.
- The service supports three search domains: documents, publications,
  and notes. Each domain has its own method; a combined search method
  is provided for callers that need a unified result set.
- The service never modifies the index.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from academic_platform.infrastructure.database.models.fts import (
    FTS_DOCUMENTS_TABLE,
    FTS_NOTES_TABLE,
    FTS_PUBLICATIONS_TABLE,
)
from academic_platform.infrastructure.full_text_search.errors import (
    FtsQueryError,
)

_logger = logging.getLogger(__name__)


#: Marker strings used to highlight matched terms within snippets. The
#: markers are inserted by FTS5; the presentation layer replaces them
#: with the UI's highlight styling.
SNIPPET_START_MARKER = "[["
SNIPPET_END_MARKER = "]]"


@dataclass(frozen=True, slots=True)
class FtsSnippet:
    """A snippet produced by the FTS5 ``snippet`` function."""

    text: str
    start_marker: str = SNIPPET_START_MARKER
    end_marker: str = SNIPPET_END_MARKER

    def plain(self) -> str:
        """Return the snippet with the highlight markers removed."""
        return self.text.replace(self.start_marker, "").replace(
            self.end_marker, ""
        )


@dataclass(frozen=True, slots=True)
class FtsSearchResult:
    """A single FTS5 search hit."""

    domain: str
    identifier: str
    rank: float
    snippet: FtsSnippet
    page_number: int | None = None
    metadata: dict[str, str] = field(default_factory=dict)


class FtsQueryService:
    """Execute MATCH queries against the FTS5 tables."""

    def __init__(self, session) -> None:
        self._session = session

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def search_documents(
        self,
        query: str,
        *,
        limit: int = 50,
        snippet_column: str = "content",
        snippet_tokens: int = 16,
    ) -> list[FtsSearchResult]:
        """Search the document FTS5 table."""
        self._validate_query(query)
        if snippet_column not in {"title", "authors", "content"}:
            raise FtsQueryError(
                f"snippet_column must be one of: title, authors, content; "
                f"got {snippet_column!r}"
            )
        column_index = _document_column_index(snippet_column)
        statement = text(
            f"""
            SELECT
                document_key,
                chunk_index,
                page_number,
                rank,
                snippet("{FTS_DOCUMENTS_TABLE}", :column_index, :start, :end, "…", :tokens) AS snippet
            FROM "{FTS_DOCUMENTS_TABLE}"
            WHERE "{FTS_DOCUMENTS_TABLE}" MATCH :query
            ORDER BY rank
            LIMIT :limit
            """
        )
        params = {
            "query": query,
            "column_index": column_index,
            "start": SNIPPET_START_MARKER,
            "end": SNIPPET_END_MARKER,
            "tokens": snippet_tokens,
            "limit": int(limit),
        }
        try:
            rows = self._session.execute(statement, params).all()
        except SQLAlchemyError as exc:
            raise FtsQueryError(f"Document FTS query failed: {exc}") from exc
        results: list[FtsSearchResult] = []
        for row in rows:
            document_key = str(row[0])
            chunk_index = int(row[1]) if row[1] is not None else 0
            page_number = int(row[2]) if row[2] is not None else None
            rank = float(row[3]) if row[3] is not None else 0.0
            snippet_text = str(row[4]) if row[4] is not None else ""
            results.append(
                FtsSearchResult(
                    domain="document",
                    identifier=document_key,
                    rank=rank,
                    snippet=FtsSnippet(text=snippet_text),
                    page_number=page_number if page_number and page_number > 0 else None,
                    metadata={"chunk_index": str(chunk_index)},
                )
            )
        return results

    def search_publications(
        self,
        query: str,
        *,
        limit: int = 50,
        snippet_column: str = "abstract",
        snippet_tokens: int = 16,
    ) -> list[FtsSearchResult]:
        """Search the publications FTS5 table."""
        self._validate_query(query)
        if snippet_column not in {"title", "authors", "abstract", "venue"}:
            raise FtsQueryError(
                f"snippet_column must be one of: title, authors, abstract, "
                f"venue; got {snippet_column!r}"
            )
        column_index = _publication_column_index(snippet_column)
        statement = text(
            f"""
            SELECT
                publication_key,
                rank,
                snippet("{FTS_PUBLICATIONS_TABLE}", :column_index, :start, :end, "…", :tokens) AS snippet
            FROM "{FTS_PUBLICATIONS_TABLE}"
            WHERE "{FTS_PUBLICATIONS_TABLE}" MATCH :query
            ORDER BY rank
            LIMIT :limit
            """
        )
        params = {
            "query": query,
            "column_index": column_index,
            "start": SNIPPET_START_MARKER,
            "end": SNIPPET_END_MARKER,
            "tokens": snippet_tokens,
            "limit": int(limit),
        }
        try:
            rows = self._session.execute(statement, params).all()
        except SQLAlchemyError as exc:
            raise FtsQueryError(f"Publication FTS query failed: {exc}") from exc
        results: list[FtsSearchResult] = []
        for row in rows:
            publication_key = str(row[0])
            rank = float(row[1]) if row[1] is not None else 0.0
            snippet_text = str(row[2]) if row[2] is not None else ""
            results.append(
                FtsSearchResult(
                    domain="publication",
                    identifier=publication_key,
                    rank=rank,
                    snippet=FtsSnippet(text=snippet_text),
                )
            )
        return results

    def search_notes(
        self,
        query: str,
        *,
        limit: int = 50,
        snippet_tokens: int = 16,
    ) -> list[FtsSearchResult]:
        """Search the notes FTS5 table."""
        self._validate_query(query)
        statement = text(
            f"""
            SELECT
                document_key,
                annotation_id,
                page_number,
                rank,
                snippet("{FTS_NOTES_TABLE}", 3, :start, :end, "…", :tokens) AS snippet
            FROM "{FTS_NOTES_TABLE}"
            WHERE "{FTS_NOTES_TABLE}" MATCH :query
            ORDER BY rank
            LIMIT :limit
            """
        )
        params = {
            "query": query,
            "start": SNIPPET_START_MARKER,
            "end": SNIPPET_END_MARKER,
            "tokens": snippet_tokens,
            "limit": int(limit),
        }
        try:
            rows = self._session.execute(statement, params).all()
        except SQLAlchemyError as exc:
            raise FtsQueryError(f"Note FTS query failed: {exc}") from exc
        results: list[FtsSearchResult] = []
        for row in rows:
            document_key = str(row[0])
            annotation_id = int(row[1]) if row[1] is not None else 0
            page_number = int(row[2]) if row[2] is not None else None
            rank = float(row[3]) if row[3] is not None else 0.0
            snippet_text = str(row[4]) if row[4] is not None else ""
            results.append(
                FtsSearchResult(
                    domain="note",
                    identifier=str(annotation_id),
                    rank=rank,
                    snippet=FtsSnippet(text=snippet_text),
                    page_number=page_number if page_number and page_number > 0 else None,
                    metadata={
                        "document_key": document_key,
                        "annotation_id": str(annotation_id),
                    },
                )
            )
        return results

    def search_all(
        self,
        query: str,
        *,
        limit_per_domain: int = 25,
    ) -> list[FtsSearchResult]:
        """Search every domain and return a merged, rank-sorted list."""
        self._validate_query(query)
        combined: list[FtsSearchResult] = []
        combined.extend(self.search_documents(query, limit=limit_per_domain))
        combined.extend(self.search_publications(query, limit=limit_per_domain))
        combined.extend(self.search_notes(query, limit=limit_per_domain))
        combined.sort(key=lambda result: result.rank)
        return combined

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _validate_query(query: str) -> None:
        if not query or not query.strip():
            raise FtsQueryError("query must not be empty")


def _document_column_index(column: str) -> int:
    return {
        "document_key": 0,
        "chunk_index": 1,
        "page_number": 2,
        "title": 3,
        "authors": 4,
        "content": 5,
    }[column]


def _publication_column_index(column: str) -> int:
    return {
        "publication_key": 0,
        "title": 1,
        "authors": 2,
        "abstract": 3,
        "venue": 4,
    }[column]