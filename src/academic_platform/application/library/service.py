"""Application service for the personal library.

The service lists, filters, loads, and deletes library documents. It
uses the document repository for the base table and the FTS5 query
service for full-text search.

Design decisions
----------------
- The service returns immutable value objects, never ORM rows.
- Full-text search delegates to the FTS5 query service. When the
  filter's search text is present, the service resolves the FTS5
  document keys and restricts the repository query to those keys. The
  order of the FTS5 results is preserved.
- The service never touches the filesystem. It reports the file's
  existence through the ``missing`` flag that the document asset
  carries.
- The service never commits. It runs inside a unit of work supplied by
  the caller.
- Deleting a document removes the ORM row and the FTS5 rows in the same
  operation. The service does not delete the underlying file; file
  deletion is a separate operation performed by the file storage
  service.
"""

from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from academic_platform.application.library.errors import (
    LibraryEntryNotFoundError,
    LibraryError,
)
from academic_platform.application.library.model import (
    LibraryEntry,
    LibraryFilter,
    LibraryPage,
    LibrarySortDirection,
    LibrarySortField,
)
from academic_platform.infrastructure.database.models import (
    DocumentAsset,
    DocumentMetadata,
)
from academic_platform.infrastructure.full_text_search.errors import (
    FtsError,
)
from academic_platform.infrastructure.full_text_search.indexer import (
    FtsIndexer,
)
from academic_platform.infrastructure.full_text_search.query import (
    FtsQueryService,
)
from academic_platform.infrastructure.repositories.errors import (
    RepositoryError,
)
from academic_platform.infrastructure.repositories.manager import (
    RepositoryManager,
)

_logger = logging.getLogger(__name__)


_DEFAULT_LIMIT = 200
_MAX_LIMIT = 5000


class LibraryService:
    """Application service for the personal library."""

    def __init__(self, repositories: RepositoryManager) -> None:
        self._repositories = repositories

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------
    def list_entries(
        self,
        *,
        filter_state: LibraryFilter | None = None,
        sort_field: LibrarySortField = LibrarySortField.UPDATED_AT,
        sort_direction: LibrarySortDirection = LibrarySortDirection.DESCENDING,
        offset: int = 0,
        limit: int = _DEFAULT_LIMIT,
    ) -> LibraryPage:
        """Return a page of library entries filtered and sorted."""
        filter_state = filter_state or LibraryFilter()
        limit = max(1, min(limit, _MAX_LIMIT))
        offset = max(0, offset)

        ordered_keys: list[str] | None = None
        if filter_state.has_search:
            ordered_keys = self._fts_document_keys(filter_state.search_text)
            if not ordered_keys:
                return LibraryPage(entries=(), total=0, offset=offset, limit=limit)

        rows = self._fetch_rows(filter_state, sort_field, sort_direction)
        if ordered_keys is not None:
            key_order = {key: index for index, key in enumerate(ordered_keys)}
            rows = [row for row in rows if row.key in key_order]
            rows.sort(key=lambda row: key_order[row.key])

        total = len(rows)
        page_slice = rows[offset:offset + limit]
        entries = tuple(self._to_entry(row) for row in page_slice)
        return LibraryPage(
            entries=entries,
            total=total,
            offset=offset,
            limit=limit,
        )

    def get_entry(self, document_key: str) -> LibraryEntry:
        """Return the library entry for a document key.

        Raises
        ------
        LibraryEntryNotFoundError
            If no document with the key exists.
        """
        repo = self._repositories.get("document_asset")
        try:
            row = repo.find_by_key(document_key)
        except RepositoryError as exc:
            raise LibraryError(f"Unable to read document: {exc}") from exc
        if row is None:
            raise LibraryEntryNotFoundError(
                f"No document with key {document_key!r}"
            )
        return self._to_entry(row)

    def count_by_state(self) -> dict[str, int]:
        """Return the number of documents in each processing state."""
        repo = self._repositories.get("document_asset")
        try:
            rows = repo.find_all()
        except RepositoryError as exc:
            raise LibraryError(f"Unable to read documents: {exc}") from exc
        counts: dict[str, int] = {}
        for row in rows:
            counts[row.processing_state] = counts.get(row.processing_state, 0) + 1
        return counts

    def extensions_present(self) -> tuple[str, ...]:
        """Return the sorted set of extensions present in the library."""
        repo = self._repositories.get("document_asset")
        try:
            rows = repo.find_all()
        except RepositoryError as exc:
            raise LibraryError(f"Unable to read documents: {exc}") from exc
        extensions: set[str] = set()
        for row in rows:
            extension = Path(row.location).suffix.lower()
            if extension:
                extensions.add(extension)
        return tuple(sorted(extensions))

    # ------------------------------------------------------------------
    # Writes
    # ------------------------------------------------------------------
    def delete_entry(self, document_key: str) -> None:
        """Remove a document and its FTS5 rows.

        The underlying file is not deleted. File deletion is a separate
        operation performed by the file storage service when the user
        confirms it.
        """
        repo = self._repositories.get("document_asset")
        try:
            row = repo.find_by_key(document_key)
        except RepositoryError as exc:
            raise LibraryError(f"Unable to read document: {exc}") from exc
        if row is None:
            raise LibraryEntryNotFoundError(
                f"No document with key {document_key!r}"
            )
        try:
            session = repo.session
            FtsIndexer(session).remove_document(document_key)
            repo.delete(row)
        except RepositoryError as exc:
            raise LibraryError(f"Unable to delete document: {exc}") from exc
        except FtsError as exc:
            raise LibraryError(f"Unable to update the search index: {exc}") from exc

    def mark_missing(self, document_key: str) -> None:
        """Mark a document as missing."""
        self._set_missing_flag(document_key, missing=True)

    def mark_present(self, document_key: str) -> None:
        """Clear the missing flag on a document."""
        self._set_missing_flag(document_key, missing=False)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _set_missing_flag(self, document_key: str, *, missing: bool) -> None:
        repo = self._repositories.get("document_asset")
        try:
            row = repo.find_by_key(document_key)
        except RepositoryError as exc:
            raise LibraryError(f"Unable to read document: {exc}") from exc
        if row is None:
            raise LibraryEntryNotFoundError(
                f"No document with key {document_key!r}"
            )
        row.missing = 1 if missing else 0
        try:
            repo.session.flush()
        except SQLAlchemyError as exc:
            raise LibraryError(f"Unable to record the missing flag: {exc}") from exc

    def _fts_document_keys(self, query: str) -> list[str]:
        session = self._repositories.get("document_asset").session
        try:
            service = FtsQueryService(session)
            results = service.search_documents(query, limit=_MAX_LIMIT)
        except FtsError as exc:
            _logger.warning("Full-text search failed: %s", exc)
            return []
        seen: set[str] = set()
        ordered: list[str] = []
        for result in results:
            if result.identifier in seen:
                continue
            seen.add(result.identifier)
            ordered.append(result.identifier)
        return ordered

    def _fetch_rows(
        self,
        filter_state: LibraryFilter,
        sort_field: LibrarySortField,
        sort_direction: LibrarySortDirection,
    ) -> list[DocumentAsset]:
        session = self._repositories.get("document_asset").session
        statement = select(DocumentAsset)
        if filter_state.processing_states:
            statement = statement.where(
                DocumentAsset.processing_state.in_(
                    tuple(filter_state.processing_states)
                )
            )
        order_column = _sort_column(sort_field)
        if sort_direction is LibrarySortDirection.ASCENDING:
            statement = statement.order_by(order_column.asc())
        else:
            statement = statement.order_by(order_column.desc())
        try:
            rows = list(session.execute(statement).scalars().all())
        except SQLAlchemyError as exc:
            raise LibraryError(f"Unable to query documents: {exc}") from exc
        if filter_state.extensions:
            allowed = {extension.lower() for extension in filter_state.extensions}
            rows = [
                row
                for row in rows
                if Path(row.location).suffix.lower() in allowed
            ]
        return rows

    def _to_entry(self, row: DocumentAsset) -> LibraryEntry:
        extension = Path(row.location).suffix.lower()
        metadata_repo = self._repositories.get("document_metadata")
        metadata: DocumentMetadata | None = None
        try:
            metadata = metadata_repo.find_for_document(row.id)
        except RepositoryError:
            metadata = None
        authors: tuple[str, ...] = ()
        if metadata is not None and metadata.authors_json:
            authors = _load_authors(metadata.authors_json)
        return LibraryEntry(
            key=row.key,
            display_name=row.display_name or row.original_filename,
            original_filename=row.original_filename,
            storage_mode=row.storage_mode,
            location=row.location,
            extension=extension,
            size_bytes=row.size_bytes,
            page_count=row.page_count,
            processing_state=row.processing_state,
            ocr_state=row.ocr_state,
            indexing_state=row.indexing_state,
            missing=bool(row.missing),
            last_error=row.last_error or "",
            created_at=row.created_at.isoformat() if row.created_at else "",
            updated_at=row.updated_at.isoformat() if row.updated_at else "",
            title=metadata.title if metadata and metadata.title else None,
            authors=authors,
            year=metadata.year if metadata else None,
            doi=metadata.doi if metadata else None,
        )


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
def _sort_column(field: LibrarySortField):
    return {
        LibrarySortField.DISPLAY_NAME: DocumentAsset.display_name,
        LibrarySortField.ADDED_AT: DocumentAsset.created_at,
        LibrarySortField.UPDATED_AT: DocumentAsset.updated_at,
        LibrarySortField.PROCESSING_STATE: DocumentAsset.processing_state,
        LibrarySortField.SIZE: DocumentAsset.size_bytes,
    }[field]


def _load_authors(authors_json: str) -> tuple[str, ...]:
    import json

    try:
        data = json.loads(authors_json)
    except ValueError:
        return ()
    if isinstance(data, list):
        return tuple(str(item) for item in data if item)
    if isinstance(data, str):
        return (data,)
    return ()