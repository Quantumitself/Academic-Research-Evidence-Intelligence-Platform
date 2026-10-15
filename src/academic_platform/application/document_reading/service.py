"""Application service for document reading.

The service opens a document by key, resolves its file through the
document asset record, and renders pages on demand. It keeps a small
in-memory cache of recently rendered pages so that scrolling back and
forth does not re-render pages that were just displayed.

Design decisions
----------------
- The service opens the PDF lazily. The document handle is acquired on
  the first page render and released when the caller calls ``close``.
  Handles are not shared across threads.
- Page rendering uses PyMuPDF's ``get_pixmap`` with a DPI derived from
  the requested zoom level. The rendered image is encoded as PNG so
  that the bytes can be handed to Qt without further conversion in the
  service layer.
- The cache is bounded. It holds at most ``cache_size`` pages; the
  least-recently-used page is evicted when the bound is exceeded.
- The service never modifies the source PDF.
- The service never raises on a page that fails to render; the caller
  receives a ``DocumentReadingError`` that carries the page number so
  that the reader page can present an error tile in place of the page.
"""

from __future__ import annotations

import logging
from collections import OrderedDict
from pathlib import Path

import fitz  # PyMuPDF

from academic_platform.application.document_reading.errors import (
    DocumentReadingError,
    DocumentReadingNotFoundError,
    DocumentReadingUnsupportedError,
)
from academic_platform.application.document_reading.model import (
    DocumentOutlineEntry,
    RenderedPage,
)
from academic_platform.infrastructure.repositories.errors import (
    RepositoryError,
)
from academic_platform.infrastructure.repositories.manager import (
    RepositoryManager,
)

_logger = logging.getLogger(__name__)

_DEFAULT_DPI = 96
_MIN_DPI = 36
_MAX_DPI = 600
_DEFAULT_CACHE_SIZE = 8


class DocumentReaderService:
    """Open and render a document by key."""

    def __init__(
        self,
        repositories: RepositoryManager,
        *,
        cache_size: int = _DEFAULT_CACHE_SIZE,
    ) -> None:
        if cache_size < 1:
            raise ValueError("cache_size must be at least 1")
        self._repositories = repositories
        self._cache_size = cache_size
        self._cache: OrderedDict[tuple[str, int, int], RenderedPage] = OrderedDict()
        self._documents: dict[str, fitz.Document] = {}

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def open_document(self, document_key: str) -> tuple[int, tuple[DocumentOutlineEntry, ...]]:
        """Open a document and return its page count and outline.

        Raises
        ------
        DocumentReadingNotFoundError
            If the document or its file does not exist.
        DocumentReadingUnsupportedError
            If the file cannot be opened as a PDF.
        """
        document = self._acquire_document(document_key)
        try:
            page_count = int(document.page_count)
            outline = _sanitize_outline(document.get_toc(simple=False) or [])
        except Exception as exc:  # noqa: BLE001 - boundary
            raise DocumentReadingError(
                f"Unable to read document metadata: {exc}"
            ) from exc
        return page_count, outline

    def close_document(self, document_key: str) -> None:
        """Close the document handle if one is open."""
        document = self._documents.pop(document_key, None)
        if document is not None:
            try:
                document.close()
            except Exception:  # noqa: BLE001 - boundary
                _logger.exception("Unable to close document %s", document_key)
        # Evict the document's cache entries.
        keys_to_remove = [
            key for key in self._cache.keys() if key[0] == document_key
        ]
        for key in keys_to_remove:
            self._cache.pop(key, None)

    def close_all(self) -> None:
        """Close every open document handle and clear the cache."""
        for key in list(self._documents.keys()):
            self.close_document(key)
        self._cache.clear()

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------
    def render_page(
        self,
        document_key: str,
        page_number: int,
        *,
        dpi: int = _DEFAULT_DPI,
    ) -> RenderedPage:
        """Render a single page at the requested DPI.

        The page number is 1-based. The ``dpi`` value is clamped to the
        service's supported range.

        Raises
        ------
        DocumentReadingNotFoundError
            If the document or its file does not exist.
        DocumentReadingError
            If the page cannot be rendered.
        """
        dpi = _clamp(dpi, _MIN_DPI, _MAX_DPI)
        cache_key = (document_key, page_number, dpi)
        cached = self._cache.get(cache_key)
        if cached is not None:
            self._cache.move_to_end(cache_key)
            return cached

        document = self._acquire_document(document_key)
        total_pages = int(document.page_count)
        if page_number < 1 or page_number > total_pages:
            raise DocumentReadingError(
                f"Page {page_number} is outside the document's range "
                f"(1..{total_pages})"
            )
        try:
            page = document.load_page(page_number - 1)
        except Exception as exc:  # noqa: BLE001 - boundary
            raise DocumentReadingError(
                f"Unable to load page {page_number}: {exc}"
            ) from exc
        try:
            pixmap = page.get_pixmap(dpi=dpi, colorspace=fitz.csRGB, alpha=False)
        except Exception as exc:  # noqa: BLE001 - boundary
            raise DocumentReadingError(
                f"Unable to render page {page_number}: {exc}"
            ) from exc
        try:
            image_bytes = pixmap.tobytes("png")
        except Exception as exc:  # noqa: BLE001 - boundary
            raise DocumentReadingError(
                f"Unable to encode page {page_number}: {exc}"
            ) from exc

        rendered = RenderedPage(
            page_number=page_number,
            width_points=float(page.rect.width),
            height_points=float(page.rect.height),
            pixel_width=int(pixmap.width),
            pixel_height=int(pixmap.height),
            dpi=dpi,
            image_bytes=image_bytes,
        )
        self._cache[cache_key] = rendered
        while len(self._cache) > self._cache_size:
            self._cache.popitem(last=False)
        return rendered

    def page_size_points(self, document_key: str, page_number: int) -> tuple[float, float]:
        """Return the size of a page in PDF points without rendering it."""
        document = self._acquire_document(document_key)
        total_pages = int(document.page_count)
        if page_number < 1 or page_number > total_pages:
            raise DocumentReadingError(
                f"Page {page_number} is outside the document's range "
                f"(1..{total_pages})"
            )
        try:
            page = document.load_page(page_number - 1)
            return float(page.rect.width), float(page.rect.height)
        except Exception as exc:  # noqa: BLE001 - boundary
            raise DocumentReadingError(
                f"Unable to read page {page_number} dimensions: {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _acquire_document(self, document_key: str) -> fitz.Document:
        existing = self._documents.get(document_key)
        if existing is not None:
            return existing
        path = self._resolve_path(document_key)
        try:
            document = fitz.open(path)
        except Exception as exc:  # noqa: BLE001 - boundary
            raise DocumentReadingUnsupportedError(
                f"Unable to open document {document_key!r}: {exc}"
            ) from exc
        if document.is_encrypted and document.needs_pass:
            document.close()
            raise DocumentReadingUnsupportedError(
                f"Document {document_key!r} is encrypted and cannot be read."
            )
        self._documents[document_key] = document
        return document

    def _resolve_path(self, document_key: str) -> Path:
        repo = self._repositories.get("document_asset")
        try:
            row = repo.find_by_key(document_key)
        except RepositoryError as exc:
            raise DocumentReadingError(
                f"Unable to read document {document_key!r}: {exc}"
            ) from exc
        if row is None:
            raise DocumentReadingNotFoundError(
                f"No document with key {document_key!r}"
            )
        path = Path(row.location)
        if not path.exists():
            raise DocumentReadingNotFoundError(
                f"File is missing for document {document_key!r}: {path}"
            )
        if not path.is_file():
            raise DocumentReadingUnsupportedError(
                f"Document {document_key!r} does not point to a regular file."
            )
        return path


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
def _clamp(value: int, minimum: int, maximum: int) -> int:
    if value < minimum:
        return minimum
    if value > maximum:
        return maximum
    return value


def _sanitize_outline(outline: list) -> tuple[DocumentOutlineEntry, ...]:
    entries: list[DocumentOutlineEntry] = []
    for entry in outline:
        if not isinstance(entry, (list, tuple)) or len(entry) < 3:
            continue
        try:
            level = int(entry[0])
            page_number = int(entry[2])
        except (TypeError, ValueError):
            continue
        if not isinstance(entry[1], str):
            continue
        title = entry[1].strip()
        if not title:
            continue
        entries.append(
            DocumentOutlineEntry(
                level=level,
                title=title,
                page_number=page_number,
            )
        )
    return tuple(entries)