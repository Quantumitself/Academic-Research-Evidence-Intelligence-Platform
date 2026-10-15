"""Repository for document assets and their metadata, chunks, and annotations."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from academic_platform.infrastructure.database.models import (
    Annotation,
    DocumentAsset,
    DocumentChunk,
    DocumentMetadata,
)
from academic_platform.infrastructure.repositories.base import Repository
from academic_platform.infrastructure.repositories.errors import (
    EntityNotFoundError,
    RepositoryError,
)


class DocumentAssetRepository(Repository[DocumentAsset]):
    """Repository for the ``document_asset`` table."""

    entity = DocumentAsset

    def find_by_key(self, key: str) -> DocumentAsset | None:
        """Return the document with the given key, or ``None``."""
        statement = select(DocumentAsset).where(DocumentAsset.key == key).limit(1)
        try:
            return self._session.execute(statement).scalars().first()
        except SQLAlchemyError as exc:
            raise RepositoryError(f"find_by_key failed: {exc}") from exc

    def find_by_checksum(self, checksum: str) -> list[DocumentAsset]:
        """Return documents whose checksum matches the given value.

        Duplicate detection uses this method. The result may contain more
        than one row when the same file was imported under different
        storage modes.
        """
        statement = (
            select(DocumentAsset)
            .where(DocumentAsset.checksum_sha256 == checksum)
            .order_by(DocumentAsset.created_at)
        )
        try:
            return list(self._session.execute(statement).scalars().all())
        except SQLAlchemyError as exc:
            raise RepositoryError(f"find_by_checksum failed: {exc}") from exc

    def list_pending_processing(self, *, limit: int | None = None) -> list[DocumentAsset]:
        """Return documents awaiting processing, oldest first."""
        statement = (
            select(DocumentAsset)
            .where(DocumentAsset.processing_state == "pending")
            .order_by(DocumentAsset.created_at)
        )
        if limit is not None:
            statement = statement.limit(limit)
        try:
            return list(self._session.execute(statement).scalars().all())
        except SQLAlchemyError as exc:
            raise RepositoryError(f"list_pending_processing failed: {exc}") from exc

    def mark_missing(self, document_id: int) -> DocumentAsset:
        """Mark a document as missing and return the refreshed row."""
        document = self.get_or_raise(document_id)
        document.missing = 1
        try:
            self._session.flush()
        except SQLAlchemyError as exc:
            raise RepositoryError(f"mark_missing failed: {exc}") from exc
        return document

    def mark_present(self, document_id: int) -> DocumentAsset:
        """Clear the missing flag and return the refreshed row."""
        document = self.get_or_raise(document_id)
        document.missing = 0
        try:
            self._session.flush()
        except SQLAlchemyError as exc:
            raise RepositoryError(f"mark_present failed: {exc}") from exc
        return document


class DocumentMetadataRepository(Repository[DocumentMetadata]):
    """Repository for the ``document_metadata`` table."""

    entity = DocumentMetadata

    def find_for_document(self, document_id: int) -> DocumentMetadata | None:
        """Return the metadata row for a document, or ``None``."""
        statement = (
            select(DocumentMetadata)
            .where(DocumentMetadata.document_id == document_id)
            .limit(1)
        )
        try:
            return self._session.execute(statement).scalars().first()
        except SQLAlchemyError as exc:
            raise RepositoryError(f"find_for_document failed: {exc}") from exc

    def upsert_for_document(
        self,
        document_id: int,
        *,
        title: str | None = None,
        authors_json: str | None = None,
        year: int | None = None,
        venue: str | None = None,
        doi: str | None = None,
        abstract: str | None = None,
        language: str | None = None,
        extraction_confidence: float | None = None,
        extraction_method: str = "pdf_heuristic",
    ) -> DocumentMetadata:
        """Create or replace the metadata row for a document.

        The method is not a general update; it replaces every field with
        the supplied value. Callers that need partial updates should fetch
        the row and use ``update``.
        """
        existing = self.find_for_document(document_id)
        if existing is None:
            row = DocumentMetadata(
                document_id=document_id,
                title=title,
                authors_json=authors_json,
                year=year,
                venue=venue,
                doi=doi,
                abstract=abstract,
                language=language,
                extraction_confidence=extraction_confidence,
                extraction_method=extraction_method,
            )
            return self.add(row)
        existing.title = title
        existing.authors_json = authors_json
        existing.year = year
        existing.venue = venue
        existing.doi = doi
        existing.abstract = abstract
        existing.language = language
        existing.extraction_confidence = extraction_confidence
        existing.extraction_method = extraction_method
        try:
            self._session.flush()
        except SQLAlchemyError as exc:
            raise RepositoryError(f"upsert_for_document failed: {exc}") from exc
        return existing


class DocumentChunkRepository(Repository[DocumentChunk]):
    """Repository for the ``document_chunk`` table."""

    entity = DocumentChunk

    def list_for_document(self, document_id: int) -> list[DocumentChunk]:
        """Return the chunks of a document ordered by chunk index."""
        statement = (
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document_id)
            .order_by(DocumentChunk.chunk_index)
        )
        try:
            return list(self._session.execute(statement).scalars().all())
        except SQLAlchemyError as exc:
            raise RepositoryError(f"list_for_document failed: {exc}") from exc

    def chunks_for_page(self, document_id: int, page_number: int) -> list[DocumentChunk]:
        """Return the chunks of a document on a specific page."""
        statement = (
            select(DocumentChunk)
            .where(
                DocumentChunk.document_id == document_id,
                DocumentChunk.page_number == page_number,
            )
            .order_by(DocumentChunk.chunk_index)
        )
        try:
            return list(self._session.execute(statement).scalars().all())
        except SQLAlchemyError as exc:
            raise RepositoryError(f"chunks_for_page failed: {exc}") from exc

    def replace_for_document(
        self,
        document_id: int,
        chunks: list[DocumentChunk],
    ) -> list[DocumentChunk]:
        """Replace every chunk of a document with the supplied list.

        The previous chunks are deleted and the new chunks are inserted
        within a single flush. The caller must have constructed the new
        chunks with the correct ``document_id``.
        """
        try:
            self._session.query(DocumentChunk).filter(
                DocumentChunk.document_id == document_id
            ).delete(synchronize_session=False)
            self._session.add_all(chunks)
            self._session.flush()
        except SQLAlchemyError as exc:
            raise RepositoryError(f"replace_for_document failed: {exc}") from exc
        return chunks

    def count_for_document(self, document_id: int) -> int:
        """Return the number of chunks belonging to a document."""
        statement = select(DocumentChunk).where(
            DocumentChunk.document_id == document_id
        )
        try:
            return len(list(self._session.execute(statement).scalars().all()))
        except SQLAlchemyError as exc:
            raise RepositoryError(f"count_for_document failed: {exc}") from exc


class AnnotationRepository(Repository[Annotation]):
    """Repository for the ``annotation`` table."""

    entity = Annotation

    def list_for_document(self, document_id: int) -> list[Annotation]:
        """Return the annotations of a document ordered by page and id."""
        statement = (
            select(Annotation)
            .where(Annotation.document_id == document_id)
            .order_by(Annotation.page_number, Annotation.id)
        )
        try:
            return list(self._session.execute(statement).scalars().all())
        except SQLAlchemyError as exc:
            raise RepositoryError(f"list_for_document failed: {exc}") from exc

    def list_for_page(self, document_id: int, page_number: int) -> list[Annotation]:
        """Return the annotations on a specific page."""
        statement = (
            select(Annotation)
            .where(
                Annotation.document_id == document_id,
                Annotation.page_number == page_number,
            )
            .order_by(Annotation.id)
        )
        try:
            return list(self._session.execute(statement).scalars().all())
        except SQLAlchemyError as exc:
            raise RepositoryError(f"list_for_page failed: {exc}") from exc

    def list_bookmarks(self, document_id: int) -> list[Annotation]:
        """Return the bookmarks of a document ordered by page."""
        statement = (
            select(Annotation)
            .where(
                Annotation.document_id == document_id,
                Annotation.kind == "bookmark",
            )
            .order_by(Annotation.page_number, Annotation.id)
        )
        try:
            return list(self._session.execute(statement).scalars().all())
        except SQLAlchemyError as exc:
            raise RepositoryError(f"list_bookmarks failed: {exc}") from exc

    def require(self, annotation_id: int) -> Annotation:
        """Return the annotation with the given identifier.

        Raises
        ------
        EntityNotFoundError
            If no annotation matches the identifier.
        """
        annotation = self.get(annotation_id)
        if annotation is None:
            raise EntityNotFoundError(
                f"Annotation with id {annotation_id!r} not found"
            )
        return annotation