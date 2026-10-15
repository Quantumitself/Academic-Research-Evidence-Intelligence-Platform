"""FTS5 index rebuilder.

The rebuilder reconstructs the FTS5 tables from the primary tables. It
is used after a schema change, after a corrupted index is detected, and
during first-time setup when the FTS5 tables exist but are empty.

Design decisions
----------------
- The rebuilder runs inside a single transaction. A failure leaves the
  FTS5 tables in the state they were in before the rebuild began.
- The rebuilder processes documents, publications, and notes in
  separate passes so that progress can be reported per domain.
- The rebuilder never reads file content. It operates on values that
  the application layer has already extracted and persisted.
- The rebuilder clears every FTS5 table before repopulating it. Partial
  indexes are not left behind.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from sqlalchemy import select, text
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
    FtsRebuildError,
)
from academic_platform.infrastructure.full_text_search.indexer import (
    FtsIndexer,
)

_logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class FtsRebuildReport:
    """Outcome of a full index rebuild."""

    documents_indexed: int = 0
    document_chunks_indexed: int = 0
    publications_indexed: int = 0
    annotations_indexed: int = 0
    warnings: tuple[str, ...] = field(default_factory=tuple)


class FtsRebuilder:
    """Reconstruct the FTS5 index from the primary tables."""

    def __init__(self, session) -> None:
        self._session = session
        self._indexer = FtsIndexer(session)

    def rebuild(self) -> FtsRebuildReport:
        """Rebuild every FTS5 table.

        Raises
        ------
        FtsRebuildError
            If the rebuild cannot be completed.
        """
        self._clear_tables()

        documents_indexed = 0
        chunks_indexed = 0
        publications_indexed = 0
        annotations_indexed = 0
        warnings: list[str] = []

        try:
            documents_indexed, chunks_indexed, document_warnings = (
                self._rebuild_documents()
            )
            warnings.extend(document_warnings)

            publications_indexed, publication_warnings = (
                self._rebuild_publications()
            )
            warnings.extend(publication_warnings)

            annotations_indexed, note_warnings = self._rebuild_annotations()
            warnings.extend(note_warnings)
        except FtsRebuildError:
            raise
        except Exception as exc:  # noqa: BLE001 - boundary
            raise FtsRebuildError(f"Index rebuild failed: {exc}") from exc

        return FtsRebuildReport(
            documents_indexed=documents_indexed,
            document_chunks_indexed=chunks_indexed,
            publications_indexed=publications_indexed,
            annotations_indexed=annotations_indexed,
            warnings=tuple(warnings),
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _clear_tables(self) -> None:
        for table_name in (
            FTS_NOTES_TABLE,
            FTS_PUBLICATIONS_TABLE,
            FTS_DOCUMENTS_TABLE,
        ):
            try:
                self._session.execute(text(f'DELETE FROM "{table_name}"'))
            except SQLAlchemyError as exc:
                raise FtsRebuildError(
                    f"Unable to clear {table_name}: {exc}"
                ) from exc

    def _rebuild_documents(self) -> tuple[int, int, list[str]]:
        warnings: list[str] = []
        documents_indexed = 0
        chunks_indexed = 0
        try:
            documents = list(
                self._session.execute(select(DocumentAsset)).scalars().all()
            )
        except SQLAlchemyError as exc:
            raise FtsRebuildError(
                f"Unable to read documents: {exc}"
            ) from exc
        for document in documents:
            try:
                chunks = list(
                    self._session.execute(
                        select(DocumentChunk)
                        .where(DocumentChunk.document_id == document.id)
                        .order_by(DocumentChunk.chunk_index)
                    ).scalars().all()
                )
                metadata = self._session.execute(
                    select(DocumentMetadata)
                    .where(DocumentMetadata.document_id == document.id)
                    .limit(1)
                ).scalars().first()
            except SQLAlchemyError as exc:
                warnings.append(
                    f"Unable to read chunks for {document.key!r}: {exc}"
                )
                continue
            try:
                written = self._indexer.index_document(document, chunks, metadata)
            except FtsRebuildError as exc:
                warnings.append(
                    f"Unable to index document {document.key!r}: {exc}"
                )
                continue
            documents_indexed += 1
            chunks_indexed += written
        return documents_indexed, chunks_indexed, warnings

    def _rebuild_publications(self) -> tuple[int, list[str]]:
        warnings: list[str] = []
        publications_indexed = 0
        try:
            publications = list(
                self._session.execute(select(Publication)).scalars().all()
            )
        except SQLAlchemyError as exc:
            raise FtsRebuildError(
                f"Unable to read publications: {exc}"
            ) from exc
        for publication in publications:
            try:
                self._indexer.index_publication(publication)
            except FtsRebuildError as exc:
                warnings.append(
                    f"Unable to index publication {publication.key!r}: {exc}"
                )
                continue
            publications_indexed += 1
        return publications_indexed, warnings

    def _rebuild_annotations(self) -> tuple[int, list[str]]:
        warnings: list[str] = []
        annotations_indexed = 0
        try:
            annotations = list(
                self._session.execute(select(Annotation)).scalars().all()
            )
        except SQLAlchemyError as exc:
            raise FtsRebuildError(
                f"Unable to read annotations: {exc}"
            ) from exc
        for annotation in annotations:
            try:
                document = self._session.get(
                    DocumentAsset, annotation.document_id
                )
            except SQLAlchemyError:
                document = None
            if document is None:
                continue
            try:
                written = self._indexer.index_annotation(annotation, document.key)
            except FtsRebuildError as exc:
                warnings.append(
                    f"Unable to index annotation {annotation.id!r}: {exc}"
                )
                continue
            annotations_indexed += written
        return annotations_indexed, warnings