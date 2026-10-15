"""Application service wrapping the PDF extractor.

The service extracts a stored document by key, persists the extracted
chunks and metadata, and advances the document asset's processing
state. It is the single entry point that the presentation layer and the
background pipeline use.

Design decisions
----------------
- The service never modifies the PDF file. It opens the file read-only
  through the extractor.
- The service replaces every chunk of a document on each extraction
  run. This is deliberate: chunks are derived from the file and must
  reflect the latest extraction. The previous chunks are dropped in the
  same transaction.
- The service never overwrites user-edited metadata. When a metadata
  row exists and has been reviewed by the user, the service leaves it
  untouched. When the row is unreviewed, the service replaces it with
  the newly extracted values.
- The service never commits. It runs inside a unit of work supplied by
  the caller.
- The service records the extraction outcome on the document asset's
  ``last_error`` field and advances ``processing_state`` to ``extracted``
  on success or ``failed`` on failure. The ``processing_version`` field
  is incremented on every successful extraction so that downstream
  consumers can detect changes.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from academic_platform.application.document_extraction.errors import (
    DocumentExtractionError,
    DocumentNotFoundError,
)
from academic_platform.infrastructure.database.models import (
    DocumentAsset,
    DocumentChunk,
    DocumentMetadata,
)
from academic_platform.infrastructure.document_processing import (
    DocumentProcessingError,
    PdfExtractionResult,
    PdfTextExtractor,
)
from academic_platform.infrastructure.repositories.errors import (
    RepositoryError,
)
from academic_platform.infrastructure.repositories.manager import (
    RepositoryManager,
)
from academic_platform.infrastructure.document_processing.metadata_extractor import (
    PdfMetadataExtraction,
    PdfMetadataExtractor,
)
from academic_platform.infrastructure.document_processing.ocr_config import (
    OcrConfig,
)
from academic_platform.infrastructure.document_processing.ocr_errors import (
    OcrError,
    OcrUnavailableError,
)
from academic_platform.infrastructure.document_processing.ocr_extractor import (
    PdfOcrExtractor,
)
from academic_platform.infrastructure.full_text_search.indexer import (
    FtsIndexer,
)


_logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ExtractionOutcome:
    """Result of extracting a single document."""

    document_key: str
    page_count: int
    extracted_page_count: int
    chunk_count: int
    truncated: bool
    warnings: tuple[str, ...]


class DocumentExtractionService:
    """Extract text and metadata from a stored document."""

    def __init__(
        self,
        repositories: RepositoryManager,
        extractor: PdfTextExtractor | None = None,
        metadata_extractor: PdfMetadataExtractor | None = None,
        ocr_extractor: PdfOcrExtractor | None = None,
        *,
        ocr_config: OcrConfig | None = None,
        ocr_enabled: bool = False,
        index_enabled: bool = True,
    ) -> None:
        self._repositories = repositories
        self._extractor = extractor or PdfTextExtractor()
        self._metadata_extractor = metadata_extractor or PdfMetadataExtractor(
            text_extractor=self._extractor,
        )
        self._ocr_config = ocr_config
        self._ocr_enabled = ocr_enabled
        self._ocr_extractor = ocr_extractor
        self._index_enabled = index_enabled

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def extract_document(self, document_key: str) -> ExtractionOutcome:
        document_repo = self._repositories.get("document_asset")
        try:
            document = document_repo.find_by_key(document_key)
        except RepositoryError as exc:
            raise DocumentExtractionError(
                f"Unable to read document {document_key!r}: {exc}"
            ) from exc
        if document is None:
            raise DocumentNotFoundError(
                f"No document with key {document_key!r}"
            )

        path = Path(document.location)
        if not path.exists():
            self._mark_failed(document, message=f"File is missing: {path}")
            raise DocumentExtractionError(
                f"File is missing for document {document_key!r}: {path}"
            )

        # Phase 1: attempt native text extraction.
        try:
            native_result = self._extractor.extract(path)
        except DocumentProcessingError as exc:
            self._mark_failed(document, message=str(exc))
            raise DocumentExtractionError(str(exc)) from exc

        result = native_result
        ocr_applied = False
        ocr_warning = ""

        # Phase 2: decide whether OCR is required.
        if self._ocr_enabled and _needs_ocr(native_result):
            try:
                ocr_extractor = self._ocr_extractor or PdfOcrExtractor(
                    self._ocr_config or OcrConfig()
                )
                ocr_result = ocr_extractor.extract(path)
                result = ocr_result
                ocr_applied = True
                document.ocr_state = "completed"
            except OcrUnavailableError as exc:
                ocr_warning = str(exc)
                document.ocr_state = "failed"
                _logger.warning(
                    "OCR is enabled but unavailable for %s: %s",
                    document_key,
                    exc,
                )
            except OcrError as exc:
                ocr_warning = str(exc)
                document.ocr_state = "failed"
                _logger.warning(
                    "OCR failed for %s: %s", document_key, exc
                )
            except Exception as exc:  # noqa: BLE001 - boundary
                ocr_warning = f"Unexpected OCR error: {exc}"
                document.ocr_state = "failed"
                _logger.exception(
                    "Unexpected OCR error for %s", document_key
                )
        elif self._ocr_enabled:
            document.ocr_state = "not_required"

        chunk_count = self._persist_chunks(document, result)
        self._persist_metadata(document, result)
        self._mark_succeeded(
            document,
            page_count=result.page_count,
            ocr_applied=ocr_applied,
        )

        if self._index_enabled:
            self._update_index(document)

        warnings = list(result.warnings)
        if ocr_warning:
            warnings.append(ocr_warning)

        return ExtractionOutcome(
            document_key=document_key,
            page_count=result.page_count,
            extracted_page_count=result.extracted_page_count,
            chunk_count=chunk_count,
            truncated=result.truncated,
            warnings=tuple(warnings),
        )

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------
    def _persist_chunks(
        self,
        document: DocumentAsset,
        result: PdfExtractionResult,
    ) -> int:
        chunk_repo = self._repositories.get("document_chunk")
        chunks: list[DocumentChunk] = []
        index = 0
        for page in result.pages:
            if not page.text:
                continue
            chunks.append(
                DocumentChunk(
                    document_id=document.id,
                    chunk_index=index,
                    page_number=page.page_number,
                    section_title=None,
                    content=page.text,
                    token_count=None,
                )
            )
            index += 1
        if not chunks:
            return 0
        try:
            chunk_repo.replace_for_document(document.id, chunks)
        except RepositoryError as exc:
            raise DocumentExtractionError(
                f"Unable to persist chunks for {document.key!r}: {exc}"
            ) from exc
        return len(chunks)

    def _persist_metadata(
        self,
        document: DocumentAsset,
        result: PdfExtractionResult,
    ) -> None:
        metadata_repo = self._repositories.get("document_metadata")
        existing: DocumentMetadata | None = None
        try:
            existing = metadata_repo.find_for_document(document.id)
        except RepositoryError as exc:
            _logger.warning(
                "Unable to read existing metadata for %s: %s", document.key, exc
            )
            return
        if existing is not None and existing.reviewed_by_user:
            return

        try:
            extracted: PdfMetadataExtraction = self._metadata_extractor.extract_from_result(
                result
            )
        except DocumentProcessingError as exc:
            _logger.warning(
                "Metadata extraction failed for %s: %s", document.key, exc
            )
            return

        authors_json = _authors_to_json(extracted.authors)
        confidence = _overall_confidence(extracted)
        try:
            metadata_repo.upsert_for_document(
                document.id,
                title=extracted.title,
                authors_json=authors_json,
                year=extracted.year,
                venue=extracted.venue,
                doi=extracted.doi,
                abstract=extracted.abstract,
                language=extracted.language,
                extraction_confidence=confidence,
                extraction_method="pdf_heuristic",
            )
        except RepositoryError as exc:
            _logger.warning(
                "Unable to persist metadata for %s: %s", document.key, exc
            )

    # ------------------------------------------------------------------
    # State transitions
    # ------------------------------------------------------------------
    def _mark_succeeded(
        self,
        document: DocumentAsset,
        *,
        page_count: int,
        ocr_applied: bool = False,
    ) -> None:
        document.processing_state = "extracted"
        document.processing_version = (document.processing_version or 1) + 1
        document.page_count = page_count
        document.last_error = None
        if ocr_applied:
            document.ocr_state = "completed"
        try:
            self._repositories.get("document_asset").session.flush()
        except RepositoryError as exc:
            _logger.warning(
                "Unable to record success for %s: %s", document.key, exc
            )

    def _mark_failed(self, document: DocumentAsset, *, message: str) -> None:
        document.processing_state = "failed"
        document.last_error = message[:4096]
        try:
            self._repositories.get("document_asset").session.flush()
        except RepositoryError as exc:
            _logger.warning(
                "Unable to record failure for %s: %s", document.key, exc
            )

    def _update_index(self, document: DocumentAsset) -> None:
        """Refresh the FTS5 index rows for a document."""
        try:
            chunk_repo = self._repositories.get("document_chunk")
            metadata_repo = self._repositories.get("document_metadata")
            chunks = chunk_repo.list_for_document(document.id)
            metadata = metadata_repo.find_for_document(document.id)
        except RepositoryError as exc:
            _logger.warning(
                "Unable to read chunks/metadata for %s; index not updated: %s",
                document.key,
                exc,
            )
            return
        try:
            session = self._repositories.get("document_asset").session
            indexer = FtsIndexer(session)
            indexer.index_document(document, chunks, metadata)
        except Exception as exc:  # noqa: BLE001 - boundary
            _logger.warning(
                "Unable to update the FTS index for %s: %s", document.key, exc
            )


def _authors_to_json(authors: tuple[str, ...]) -> str | None:
    import json

    cleaned = [author.strip() for author in authors if author and author.strip()]
    if not cleaned:
        return None
    return json.dumps(cleaned)


def _overall_confidence(extracted: PdfMetadataExtraction) -> float | None:
    """Return a single confidence value summarizing the extraction.

    The value is the arithmetic mean of the per-field confidences for
    fields that were extracted. Fields that were not extracted are
    excluded from the average so that a document with only a title does
    not receive an artificially low score.
    """
    values: list[float] = []
    confidence = extracted.confidence
    if extracted.title:
        values.append(confidence.title)
    if extracted.authors:
        values.append(confidence.authors)
    if extracted.year is not None:
        values.append(confidence.year)
    if extracted.venue:
        values.append(confidence.venue)
    if extracted.doi:
        values.append(confidence.doi)
    if extracted.abstract:
        values.append(confidence.abstract)
    if extracted.language:
        values.append(confidence.language)
    if not values:
        return None
    return sum(values) / len(values)

def _needs_ocr(result: PdfExtractionResult) -> bool:
    """Return True when a document appears to require OCR.

    A document requires OCR when either:

    - It has at least one page but no page produced any text, or
    - The total extracted text is very small relative to the page count
      (fewer than 16 characters per page on average).
    """
    if not result.pages:
        return False
    total_text = sum(len(page.text.strip()) for page in result.pages)
    if total_text == 0:
        return True
    average = total_text / max(1, len(result.pages))
    return average < 16.0