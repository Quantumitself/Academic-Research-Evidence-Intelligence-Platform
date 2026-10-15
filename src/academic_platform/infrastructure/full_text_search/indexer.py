"""FTS5 index writer.

The indexer mirrors document chunks, publication metadata, and note
content into the FTS5 virtual tables. It is the only component that
writes to the FTS5 tables.

Design decisions
----------------
- FTS5 does not support row identifiers the way ordinary tables do.
  Each FTS5 row is identified by its ``rowid``. The indexer assigns
  deterministic rowids derived from the underlying entity so that
  updates and deletions are precise: the same document chunk, the same
  publication, or the same annotation always resolves to the same FTS5
  row.
- Deletion and insertion are executed in the same transaction. A failed
  insertion does not leave a stale row.
- The indexer never reads file content. It operates on values that the
  application layer has already extracted and persisted.
- The indexer accepts SQLAlchemy session objects and DBAPI connections.
  It prefers a session so that its work participates in the caller's
  unit of work.
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from academic_platform.infrastructure.database.models import (
    Annotation,
    DocumentAsset,
    DocumentChunk,
    DocumentMetadata,
    Publication,
)
from academic_platform.infrastructure.database.models.fts import (
    FTS_DOCUMENTS_TABLE,
    FTS_NOTES_TABLE,
    FTS_PUBLICATIONS_TABLE,
)
from academic_platform.infrastructure.full_text_search.errors import (
    FtsIndexError,
)

_logger = logging.getLogger(__name__)

_ROWID_MODULUS = 2**62  # FTS5 rowids are signed 64-bit integers.


class FtsIndexer:
    """Write document, publication, and note content into FTS5 tables."""

    def __init__(self, session) -> None:
        self._session = session

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def index_document(
        self,
        document: DocumentAsset,
        chunks: list[DocumentChunk],
        metadata: DocumentMetadata | None = None,
    ) -> int:
        """Index every chunk of a document and its metadata.

        Returns the number of FTS5 rows written.
        """
        self._delete_document_rows(document.key)
        title = metadata.title if metadata and metadata.title else (
            document.display_name or ""
        )
        authors = metadata.authors_json if metadata else None
        authors_text = _authors_text(authors)
        rows: list[dict[str, Any]] = []
        for chunk in chunks:
            if not chunk.content or not chunk.content.strip():
                continue
            rows.append(
                {
                    "rowid": _rowid_for_chunk(document.key, chunk.chunk_index),
                    "document_key": document.key,
                    "chunk_index": chunk.chunk_index,
                    "page_number": chunk.page_number or 0,
                    "title": title,
                    "authors": authors_text,
                    "content": chunk.content,
                }
            )
        if not rows:
            return 0
        self._insert_document_rows(rows)
        return len(rows)

    def remove_document(self, document_key: str) -> int:
        """Remove every FTS5 row belonging to a document.

        Returns the number of rows removed, when the database reports it.
        """
        return self._delete_document_rows(document_key)

    def index_publication(self, publication: Publication) -> int:
        """Index a publication's title, authors, abstract, and venue."""
        self._delete_publication_row(publication.key)
        authors_text = _authors_text(publication.authors_json)
        row = {
            "rowid": _rowid_for_publication(publication.key),
            "publication_key": publication.key,
            "title": publication.title or "",
            "authors": authors_text,
            "abstract": publication.abstract or "",
            "venue": publication.venue or "",
        }
        self._insert_publication_row(row)
        return 1

    def remove_publication(self, publication_key: str) -> int:
        """Remove a publication's FTS5 row."""
        return self._delete_publication_row(publication_key)

    def index_annotation(
        self,
        annotation: Annotation,
        document_key: str,
    ) -> int:
        """Index a single annotation's note and excerpt text."""
        self._delete_note_row(annotation.id)
        content_parts = [
            annotation.body or "",
            annotation.text_excerpt or "",
        ]
        content = " ".join(part for part in content_parts if part.strip())
        if not content:
            return 0
        row = {
            "rowid": _rowid_for_annotation(annotation.id),
            "document_key": document_key,
            "annotation_id": annotation.id,
            "page_number": annotation.page_number or 0,
            "content": content,
        }
        self._insert_note_row(row)
        return 1

    def remove_annotation(self, annotation_id: int) -> int:
        """Remove a single annotation's FTS5 row."""
        return self._delete_note_row(annotation_id)

    # ------------------------------------------------------------------
    # Document rows
    # ------------------------------------------------------------------
    def _insert_document_rows(self, rows: list[dict[str, Any]]) -> None:
        statement = text(
            f"""
            INSERT INTO "{FTS_DOCUMENTS_TABLE}"
                (rowid, document_key, chunk_index, page_number, title, authors, content)
            VALUES
                (:rowid, :document_key, :chunk_index, :page_number, :title, :authors, :content)
            """
        )
        try:
            self._session.execute(statement, rows)
        except SQLAlchemyError as exc:
            raise FtsIndexError(f"Unable to index document chunks: {exc}") from exc

    def _delete_document_rows(self, document_key: str) -> int:
        statement = text(
            f'DELETE FROM "{FTS_DOCUMENTS_TABLE}" WHERE document_key = :document_key'
        )
        try:
            result = self._session.execute(statement, {"document_key": document_key})
        except SQLAlchemyError as exc:
            raise FtsIndexError(
                f"Unable to remove document rows for {document_key!r}: {exc}"
            ) from exc
        try:
            return int(result.rowcount or 0)
        except Exception:
            return 0

    # ------------------------------------------------------------------
    # Publication rows
    # ------------------------------------------------------------------
    def _insert_publication_row(self, row: dict[str, Any]) -> None:
        statement = text(
            f"""
            INSERT INTO "{FTS_PUBLICATIONS_TABLE}"
                (rowid, publication_key, title, authors, abstract, venue)
            VALUES
                (:rowid, :publication_key, :title, :authors, :abstract, :venue)
            """
        )
        try:
            self._session.execute(statement, row)
        except SQLAlchemyError as exc:
            raise FtsIndexError(f"Unable to index publication: {exc}") from exc

    def _delete_publication_row(self, publication_key: str) -> int:
        statement = text(
            f'DELETE FROM "{FTS_PUBLICATIONS_TABLE}" WHERE publication_key = :publication_key'
        )
        try:
            result = self._session.execute(
                statement, {"publication_key": publication_key}
            )
        except SQLAlchemyError as exc:
            raise FtsIndexError(
                f"Unable to remove publication {publication_key!r}: {exc}"
            ) from exc
        try:
            return int(result.rowcount or 0)
        except Exception:
            return 0

    # ------------------------------------------------------------------
    # Note rows
    # ------------------------------------------------------------------
    def _insert_note_row(self, row: dict[str, Any]) -> None:
        statement = text(
            f"""
            INSERT INTO "{FTS_NOTES_TABLE}"
                (rowid, document_key, annotation_id, page_number, content)
            VALUES
                (:rowid, :document_key, :annotation_id, :page_number, :content)
            """
        )
        try:
            self._session.execute(statement, row)
        except SQLAlchemyError as exc:
            raise FtsIndexError(f"Unable to index annotation: {exc}") from exc

    def _delete_note_row(self, annotation_id: int) -> int:
        statement = text(
            f'DELETE FROM "{FTS_NOTES_TABLE}" WHERE annotation_id = :annotation_id'
        )
        try:
            result = self._session.execute(
                statement, {"annotation_id": annotation_id}
            )
        except SQLAlchemyError as exc:
            raise FtsIndexError(
                f"Unable to remove annotation {annotation_id!r}: {exc}"
            ) from exc
        try:
            return int(result.rowcount or 0)
        except Exception:
            return 0


# ----------------------------------------------------------------------
# Rowid derivation
# ----------------------------------------------------------------------
def _rowid_for_chunk(document_key: str, chunk_index: int) -> int:
    seed = f"doc:{document_key}:{chunk_index}"
    return _positive_rowid(seed)


def _rowid_for_publication(publication_key: str) -> int:
    seed = f"pub:{publication_key}"
    return _positive_rowid(seed)


def _rowid_for_annotation(annotation_id: int) -> int:
    seed = f"note:{annotation_id}"
    return _positive_rowid(seed)


def _positive_rowid(seed: str) -> int:
    digest = hashlib.sha256(seed.encode("utf-8")).digest()
    value = int.from_bytes(digest[:8], "big", signed=False)
    return value % _ROWID_MODULUS


# ----------------------------------------------------------------------
# Text helpers
# ----------------------------------------------------------------------
def _authors_text(authors_json: str | None) -> str:
    if not authors_json:
        return ""
    import json

    try:
        data = json.loads(authors_json)
    except ValueError:
        return ""
    if isinstance(data, list):
        return " ".join(str(item) for item in data if item)
    if isinstance(data, str):
        return data
    return ""