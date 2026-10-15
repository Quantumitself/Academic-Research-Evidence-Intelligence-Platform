"""OCR extraction for scanned PDFs.

The extractor renders each PDF page to a raster image through PyMuPDF
and passes the image to Tesseract through the ``pytesseract`` wrapper.
It returns a ``PdfExtractionResult``-compatible structure so that
downstream consumers do not need to distinguish OCR-produced text from
extractor-produced text.

Design decisions
----------------
- The extractor never modifies the source PDF. It reads pages through
  PyMuPDF and writes raster images in memory only.
- The extractor probes Tesseract's availability once per instance. A
  missing binary is reported through ``OcrUnavailableError``; the
  caller decides whether to fall back to the non-OCR extractor.
- Pages are processed one at a time. The raster image for a page is
  released as soon as Tesseract returns, so memory usage stays bounded
  even for long documents.
- In non-strict mode, a page-level failure is recorded as a warning on
  that page and extraction continues. In strict mode, the first failure
  aborts the extraction.
- The extractor produces text blocks by running Tesseract's
  ``image_to_data`` for word-level bounding boxes when
  ``preserve_blocks`` is enabled. When it is disabled, blocks are
  omitted and only page-level text is produced.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import fitz  # PyMuPDF

from academic_platform.infrastructure.document_processing.errors import (
    PdfEncryptedError,
    PdfExtractionError,
    PdfMissingError,
    PdfNotReadableError,
    PdfUnsupportedError,
)
from academic_platform.infrastructure.document_processing.ocr_config import (
    OcrConfig,
)
from academic_platform.infrastructure.document_processing.ocr_errors import (
    OcrLanguageError,
    OcrPageError,
    OcrTimeoutError,
    OcrUnavailableError,
)
from academic_platform.infrastructure.document_processing.pdf_extractor import (
    PdfExtractionResult,
    PdfPageExtraction,
    PdfTextBlock,
)

_logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class OcrAvailability:
    """Availability information about the OCR backend."""

    available: bool
    tesseract_version: str = ""
    languages: tuple[str, ...] = ()
    message: str = ""


class PdfOcrExtractor:
    """Extract text from scanned PDFs by running Tesseract on page rasters."""

    def __init__(self, config: OcrConfig | None = None) -> None:
        self._config = config or OcrConfig()

    @property
    def config(self) -> OcrConfig:
        return self._config

    # ------------------------------------------------------------------
    # Availability
    # ------------------------------------------------------------------
    def probe_availability(self) -> OcrAvailability:
        """Return availability information for the OCR backend.

        The method never raises. It reports the reason a backend is not
        available so that the caller can present an actionable message.
        """
        try:
            import pytesseract  # type: ignore[import-not-found]
        except ImportError as exc:
            return OcrAvailability(
                available=False,
                message=(
                    "The pytesseract wrapper is not installed. Install "
                    "it with: pip install pytesseract"
                ),
            )
        try:
            version = pytesseract.get_tesseract_version()
        except Exception as exc:  # noqa: BLE001 - boundary
            return OcrAvailability(
                available=False,
                message=(
                    "The Tesseract binary is not available. Install "
                    f"Tesseract and ensure it is on the PATH. ({exc})"
                ),
            )
        try:
            languages = tuple(sorted(pytesseract.get_languages(config="")))
        except Exception:  # noqa: BLE001 - boundary
            languages = ()
        return OcrAvailability(
            available=True,
            tesseract_version=str(version),
            languages=languages,
        )

    # ------------------------------------------------------------------
    # Extraction
    # ------------------------------------------------------------------
    def extract(self, path: Path) -> PdfExtractionResult:
        """Extract text from a scanned PDF using OCR.

        Raises
        ------
        OcrUnavailableError
            If the OCR backend is not available.
        PdfMissingError, PdfNotReadableError, PdfEncryptedError,
        PdfUnsupportedError
            If the PDF cannot be opened.
        PdfExtractionError
            If a page-level failure occurs while ``strict`` is True.
        """
        availability = self.probe_availability()
        if not availability.available:
            raise OcrUnavailableError(availability.message)
        self._validate_language(availability)

        resolved = self._validate_path(path)
        document = self._open_document(resolved)
        try:
            return self._extract_from_document(resolved, document)
        finally:
            document.close()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _validate_language(self, availability: OcrAvailability) -> None:
        if not availability.languages:
            return
        requested = self._config.tesseract_language.split("+")
        missing = [lang for lang in requested if lang and lang not in availability.languages]
        if missing:
            raise OcrLanguageError(
                f"Tesseract language(s) not installed: {', '.join(missing)}"
            )

    def _validate_path(self, path: Path) -> Path:
        if not isinstance(path, Path):
            raise PdfMissingError("path must be a Path instance")
        try:
            resolved = path.expanduser().resolve()
        except OSError as exc:
            raise PdfMissingError(f"Unable to resolve {path}: {exc}") from exc
        if not resolved.exists():
            raise PdfMissingError(f"PDF does not exist: {resolved}")
        if not resolved.is_file():
            raise PdfUnsupportedError(
                f"Path is not a regular file: {resolved}"
            )
        return resolved

    def _open_document(self, path: Path) -> fitz.Document:
        try:
            document = fitz.open(path)
        except Exception as exc:  # noqa: BLE001 - boundary
            raise PdfNotReadableError(
                f"Unable to open PDF {path}: {exc}"
            ) from exc
        if document.is_encrypted and document.needs_pass:
            document.close()
            raise PdfEncryptedError(
                f"PDF requires a password to open: {path}"
            )
        return document

    def _extract_from_document(
        self,
        path: Path,
        document: fitz.Document,
    ) -> PdfExtractionResult:
        total_pages = int(document.page_count)
        limit = self._config.max_pages or total_pages
        pages_to_process = min(total_pages, limit)
        truncated = pages_to_process < total_pages

        metadata = _sanitize_metadata(document.metadata or {})
        outline = _sanitize_outline(document.get_toc(simple=False) or [])

        pages: list[PdfPageExtraction] = []
        warnings: list[str] = []

        for page_index in range(pages_to_process):
            try:
                page = document.load_page(page_index)
            except Exception as exc:  # noqa: BLE001 - boundary
                message = f"Unable to load page {page_index + 1}: {exc}"
                if self._config.strict:
                    raise PdfExtractionError(
                        message, pages_extracted=len(pages)
                    ) from exc
                warnings.append(message)
                continue

            try:
                extracted = self._ocr_page(page, page_index)
            except OcrTimeoutError as exc:
                message = f"Page {page_index + 1} OCR timed out: {exc}"
                if self._config.strict:
                    raise PdfExtractionError(
                        message, pages_extracted=len(pages)
                    ) from exc
                warnings.append(message)
                pages.append(_empty_page(page, page_index, message))
                continue
            except OcrPageError as exc:
                message = f"Page {page_index + 1} OCR failed: {exc}"
                if self._config.strict:
                    raise PdfExtractionError(
                        message, pages_extracted=len(pages)
                    ) from exc
                warnings.append(message)
                pages.append(_empty_page(page, page_index, message))
                continue
            except Exception as exc:  # noqa: BLE001 - boundary
                message = f"Page {page_index + 1} OCR error: {exc}"
                if self._config.strict:
                    raise PdfExtractionError(
                        message, pages_extracted=len(pages)
                    ) from exc
                warnings.append(message)
                pages.append(_empty_page(page, page_index, message))
                continue

            pages.append(extracted)

        return PdfExtractionResult(
            path=path,
            page_count=total_pages,
            extracted_page_count=len(pages),
            metadata=metadata,
            outline=outline,
            pages=tuple(pages),
            truncated=truncated,
            warnings=tuple(warnings),
        )

    def _ocr_page(self, page: fitz.Page, page_index: int) -> PdfPageExtraction:
        import pytesseract  # type: ignore[import-not-found]

        try:
            pixmap = page.get_pixmap(
                dpi=self._config.dpi,
                colorspace=fitz.csRGB,
                alpha=False,
            )
        except Exception as exc:  # noqa: BLE001 - boundary
            raise OcrPageError(
                f"Unable to render page to a raster image: {exc}",
                page_number=page_index + 1,
            ) from exc

        try:
            image_bytes = pixmap.tobytes("png")
        except Exception as exc:  # noqa: BLE001 - boundary
            raise OcrPageError(
                f"Unable to serialize page image: {exc}",
                page_number=page_index + 1,
            ) from exc
        finally:
            # Release the pixmap as soon as possible to bound memory.
            try:
                pixmap = None
            except Exception:
                pass

        try:
            from io import BytesIO

            from PIL import Image  # type: ignore[import-not-found]

            with Image.open(BytesIO(image_bytes)) as image:
                text, blocks = self._run_tesseract(pytesseract, image, page_index)
        except (OcrPageError, OcrTimeoutError):
            # Both error types carry their own message. The outer
            # handler in ``_extract_from_document`` distinguishes them
            # and produces the appropriate warning.
            raise
        except Exception as exc:  # noqa: BLE001 - boundary
            raise OcrPageError(
                f"Unable to run Tesseract on page: {exc}",
                page_number=page_index + 1,
            ) from exc

        normalized_text = _normalize_whitespace(text)
        if len(normalized_text) < self._config.min_characters_per_page:
            # OCR produced too little text to be meaningful. The page is
            # recorded with the (short) text and marked with a warning so
            # the user can inspect it.
            return PdfPageExtraction(
                page_number=page_index + 1,
                text=normalized_text,
                blocks=blocks,
                width_points=float(page.rect.width),
                height_points=float(page.rect.height),
                warning=(
                    "OCR produced very little text; the page may be "
                    "blank, low-quality, or in an unsupported language."
                ),
            )

        return PdfPageExtraction(
            page_number=page_index + 1,
            text=normalized_text,
            blocks=blocks,
            width_points=float(page.rect.width),
            height_points=float(page.rect.height),
        )

    def _run_tesseract(
        self,
        pytesseract: Any,
        image: Any,
        page_index: int,
    ) -> tuple[str, tuple[PdfTextBlock, ...]]:
        try:
            text = pytesseract.image_to_string(
                image,
                lang=self._config.tesseract_language,
                config=self._config.tesseract_config,
                timeout=self._config.timeout_seconds,
            )
        except RuntimeError as exc:
            if "timeout" in str(exc).lower():
                raise OcrTimeoutError(
                    f"page {page_index + 1} exceeded the timeout"
                ) from exc
            raise OcrPageError(
                f"Tesseract failed: {exc}", page_number=page_index + 1
            ) from exc
        except Exception as exc:  # noqa: BLE001 - boundary
            raise OcrPageError(
                f"Tesseract failed: {exc}", page_number=page_index + 1
            ) from exc

        if not self._config.preserve_blocks:
            return text, ()
        blocks = self._extract_word_blocks(pytesseract, image, page_index)
        return text, blocks

    def _extract_word_blocks(
        self,
        pytesseract: Any,
        image: Any,
        page_index: int,
    ) -> tuple[PdfTextBlock, ...]:
        try:
            data = pytesseract.image_to_data(
                image,
                lang=self._config.tesseract_language,
                config=self._config.tesseract_config,
                timeout=self._config.timeout_seconds,
                output_type=pytesseract.Output.DICT,
            )
        except Exception:  # noqa: BLE001 - boundary
            _logger.warning(
                "Tesseract image_to_data failed on page %d; continuing "
                "without blocks.",
                page_index + 1,
            )
            return ()

        collected: list[PdfTextBlock] = []
        text_items = data.get("text", [])
        block_numbers = data.get("block_num", [])
        left = data.get("left", [])
        top = data.get("top", [])
        width = data.get("width", [])
        height = data.get("height", [])
        confidences = data.get("conf", [])

        for index, token in enumerate(text_items):
            if not isinstance(token, str):
                continue
            stripped = token.strip()
            if not stripped:
                continue
            try:
                confidence = float(confidences[index])
            except (TypeError, ValueError, IndexError):
                confidence = -1.0
            if confidence < 0:
                continue
            try:
                x0 = float(left[index])
                y0 = float(top[index])
                x1 = x0 + float(width[index])
                y1 = y0 + float(height[index])
                block_number = int(block_numbers[index])
            except (TypeError, ValueError, IndexError):
                continue
            collected.append(
                PdfTextBlock(
                    text=stripped,
                    x0=x0,
                    y0=y0,
                    x1=x1,
                    y1=y1,
                    block_index=block_number,
                )
            )
        return tuple(collected)


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
import re

_WHITESPACE_RUN = re.compile(r"[ \t]+")
_TRAILING_WHITESPACE = re.compile(r"[ \t]+$", re.MULTILINE)
_EXCESS_BLANK_LINES = re.compile(r"\n{3,}")


def _normalize_whitespace(value: str) -> str:
    without_trailing = _TRAILING_WHITESPACE.sub("", value)
    collapsed = _WHITESPACE_RUN.sub(" ", without_trailing)
    without_excess = _EXCESS_BLANK_LINES.sub("\n\n", collapsed)
    return without_excess.strip()


def _sanitize_metadata(metadata: dict) -> dict[str, str]:
    result: dict[str, str] = {}
    for key, value in metadata.items():
        if value is None:
            continue
        text = str(value).strip()
        if not text:
            continue
        result[str(key)] = text
    return result


def _sanitize_outline(outline: list) -> tuple[tuple[int, str, int], ...]:
    result: list[tuple[int, str, int]] = []
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
        result.append((level, title, page_number))
    return tuple(result)


def _empty_page(
    page: fitz.Page,
    page_index: int,
    warning: str,
) -> PdfPageExtraction:
    return PdfPageExtraction(
        page_number=page_index + 1,
        text="",
        blocks=(),
        width_points=float(page.rect.width),
        height_points=float(page.rect.height),
        warning=warning,
    )