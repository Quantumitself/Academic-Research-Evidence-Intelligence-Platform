"""PDF text extraction through PyMuPDF.

The extractor opens a PDF and returns a structured result:

- Page count and PDF metadata (title, authors, subject, keywords,
  producer, creator, creation date, modification date).
- Per-page text with whitespace normalization.
- Per-page text blocks with their bounding boxes. Blocks are returned
  as structured data so that later phases can anchor annotations to
  positions without re-extracting the page.
- Document outline (table of contents) when present.

Design decisions
----------------
- The extractor never modifies the PDF. Files are opened in read-only
  mode; no annotations are written to the file.
- The extractor never loads the entire document into memory. PyMuPDF
  loads pages on demand; the extractor reads each page, extracts its
  text and blocks, and releases the page before moving on.
- Whitespace is normalized: trailing spaces are trimmed, repeated
  spaces are collapsed to a single space, and empty lines are preserved
  only when they separate meaningful content. The normalization is
  documented on the ``normalize_whitespace`` helper.
- Encrypted PDFs are rejected with ``PdfEncryptedError`` unless a
  password is supplied. At this stage the extractor does not attempt
  to authenticate; the caller receives a descriptive error.
- The extraction is bounded by ``max_pages`` and ``max_text_bytes``
  configuration. A PDF that exceeds either bound is truncated and the
  truncation is recorded in the result.
- Extraction errors on individual pages are recorded as warnings on the
  page extraction rather than failing the entire document, unless
  ``strict`` is enabled in the configuration. Strict mode is used by
  tests and by callers that require complete extraction.
"""

from __future__ import annotations

import datetime as dt
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

import fitz  # PyMuPDF

from academic_platform.infrastructure.document_processing.errors import (
    PdfEncryptedError,
    PdfExtractionError,
    PdfMissingError,
    PdfNotReadableError,
    PdfUnsupportedError,
)

_logger = logging.getLogger(__name__)

_WHITESPACE_RUN = re.compile(r"[ \t]+")
_TRAILING_WHITESPACE = re.compile(r"[ \t]+$", re.MULTILINE)
_EXCESS_BLANK_LINES = re.compile(r"\n{3,}")


@dataclass(frozen=True, slots=True)
class PdfExtractorConfig:
    """Immutable configuration for the PDF extractor.

    Attributes
    ----------
    max_pages:
        Maximum number of pages to extract. ``None`` extracts every
        page. A truncated extraction is recorded in the result.
    max_text_bytes:
        Maximum number of bytes of extracted text (approximate, after
        normalization). ``None`` disables the limit.
    normalize:
        When True, whitespace is normalized. When False, extracted text
        is returned as PyMuPDF produced it. The default is True.
    strict:
        When True, any page-level failure aborts the entire extraction.
        When False, page-level failures are recorded as warnings and
        extraction continues with the remaining pages.
    """

    max_pages: int | None = None
    max_text_bytes: int | None = None
    normalize: bool = True
    strict: bool = False

    def __post_init__(self) -> None:
        if self.max_pages is not None and self.max_pages < 1:
            raise ValueError("max_pages must be at least 1")
        if self.max_text_bytes is not None and self.max_text_bytes < 1:
            raise ValueError("max_text_bytes must be at least 1")


@dataclass(frozen=True, slots=True)
class PdfTextBlock:
    """A single text block extracted from a page."""

    text: str
    x0: float
    y0: float
    x1: float
    y1: float
    block_index: int

    @property
    def bounding_box(self) -> tuple[float, float, float, float]:
        return (self.x0, self.y0, self.x1, self.y1)


@dataclass(frozen=True, slots=True)
class PdfPageExtraction:
    """Extraction result for a single page."""

    page_number: int  # 1-based
    text: str
    blocks: tuple[PdfTextBlock, ...] = field(default_factory=tuple)
    width_points: float = 0.0
    height_points: float = 0.0
    warning: str = ""


@dataclass(frozen=True, slots=True)
class PdfExtractionResult:
    """Extraction result for a complete PDF."""

    path: Path
    page_count: int
    extracted_page_count: int
    metadata: dict[str, str]
    outline: tuple[tuple[int, str, int], ...]
    pages: tuple[PdfPageExtraction, ...]
    truncated: bool
    warnings: tuple[str, ...] = field(default_factory=tuple)

    @property
    def total_text_bytes(self) -> int:
        return sum(len(page.text.encode("utf-8")) for page in self.pages)

    @property
    def full_text(self) -> str:
        """Return the concatenation of every page's text.

        Pages are separated by two newlines. The concatenation is
        produced on demand; callers that iterate pages should not call
        this property on large documents.
        """
        return "\n\n".join(page.text for page in self.pages)

    @property
    def is_empty(self) -> bool:
        """Return True when no page produced any text."""
        return all(not page.text for page in self.pages)


class PdfTextExtractor:
    """Extract text and structure from PDF files."""

    def __init__(self, config: PdfExtractorConfig | None = None) -> None:
        self._config = config or PdfExtractorConfig()

    @property
    def config(self) -> PdfExtractorConfig:
        return self._config

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def extract(self, path: Path) -> PdfExtractionResult:
        """Extract text and structure from a PDF.

        Raises
        ------
        PdfMissingError
            If the file does not exist.
        PdfNotReadableError
            If the file cannot be opened.
        PdfEncryptedError
            If the file is encrypted and requires a password.
        PdfUnsupportedError
            If the file is not a PDF.
        PdfExtractionError
            If a page-level failure occurs while ``strict`` is True.
        """
        resolved = self._validate_path(path)
        document = self._open_document(resolved)
        try:
            return self._extract_from_document(resolved, document)
        finally:
            document.close()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
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
        except fitz.FileDataError as exc:  # noqa: F821 - fitz exception
            raise PdfUnsupportedError(
                f"File is not a valid PDF: {path} ({exc})"
            ) from exc
        except RuntimeError as exc:
            raise PdfNotReadableError(
                f"Unable to open PDF {path}: {exc}"
            ) from exc
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
        metadata = _sanitize_metadata(document.metadata or {})
        outline = _sanitize_outline(document.get_toc(simple=False) or [])
        total_pages = int(document.page_count)
        limit = self._config.max_pages or total_pages
        pages_to_extract = min(total_pages, limit)
        truncated = pages_to_extract < total_pages

        pages: list[PdfPageExtraction] = []
        warnings: list[str] = []
        text_bytes_written = 0

        for page_index in range(pages_to_extract):
            try:
                page = document.load_page(page_index)
            except Exception as exc:  # noqa: BLE001 - boundary
                message = (
                    f"Unable to load page {page_index + 1}: {exc}"
                )
                if self._config.strict:
                    raise PdfExtractionError(
                        message, pages_extracted=len(pages)
                    ) from exc
                warnings.append(message)
                continue

            try:
                extracted, text_bytes = self._extract_page(
                    page, page_index, text_bytes_written
                )
            except Exception as exc:  # noqa: BLE001 - boundary
                message = (
                    f"Unable to extract page {page_index + 1}: {exc}"
                )
                if self._config.strict:
                    raise PdfExtractionError(
                        message, pages_extracted=len(pages)
                    ) from exc
                warnings.append(message)
                pages.append(
                    PdfPageExtraction(
                        page_number=page_index + 1,
                        text="",
                        blocks=(),
                        width_points=float(page.rect.width),
                        height_points=float(page.rect.height),
                        warning=message,
                    )
                )
                continue

            pages.append(extracted)
            text_bytes_written += text_bytes
            if (
                self._config.max_text_bytes is not None
                and text_bytes_written >= self._config.max_text_bytes
            ):
                truncated = truncated or (page_index + 1 < total_pages)
                if page_index + 1 < total_pages:
                    warnings.append(
                        f"Text extraction stopped at page {page_index + 1} "
                        f"because max_text_bytes was reached."
                    )
                break

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

    def _extract_page(
        self,
        page: fitz.Page,
        page_index: int,
        text_bytes_written: int,
    ) -> tuple[PdfPageExtraction, int]:
        try:
            raw_text = page.get_text("text") or ""
        except Exception as exc:  # noqa: BLE001 - boundary
            raise RuntimeError(f"page.get_text failed: {exc}") from exc

        if self._config.normalize:
            text = _normalize_whitespace(raw_text)
        else:
            text = raw_text

        # The text byte limit is enforced per page as well as across
        # pages. A single page that would exceed the limit is truncated
        # before the block extraction.
        if self._config.max_text_bytes is not None:
            remaining = self._config.max_text_bytes - text_bytes_written
            if remaining <= 0:
                text = ""
            else:
                encoded = text.encode("utf-8")
                if len(encoded) > remaining:
                    encoded = encoded[:remaining]
                    text = encoded.decode("utf-8", errors="ignore")

        blocks = self._extract_blocks(page)
        return (
            PdfPageExtraction(
                page_number=page_index + 1,
                text=text,
                blocks=blocks,
                width_points=float(page.rect.width),
                height_points=float(page.rect.height),
            ),
            len(text.encode("utf-8")),
        )

    def _extract_blocks(self, page: fitz.Page) -> tuple[PdfTextBlock, ...]:
        try:
            raw_blocks = page.get_text("blocks") or []
        except Exception:
            _logger.warning(
                "Unable to extract blocks from page; continuing without them"
            )
            return ()
        blocks: list[PdfTextBlock] = []
        for index, block in enumerate(raw_blocks):
            # PyMuPDF returns blocks as tuples of
            # (x0, y0, x1, y1, text, block_no, block_type).
            if not isinstance(block, (list, tuple)) or len(block) < 5:
                continue
            x0, y0, x1, y1, block_text = block[0], block[1], block[2], block[3], block[4]
            if not isinstance(block_text, str):
                continue
            normalized = (
                _normalize_whitespace(block_text)
                if self._config.normalize
                else block_text
            )
            blocks.append(
                PdfTextBlock(
                    text=normalized,
                    x0=float(x0),
                    y0=float(y0),
                    x1=float(x1),
                    y1=float(y1),
                    block_index=index,
                )
            )
        return tuple(blocks)


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
def _normalize_whitespace(value: str) -> str:
    """Return ``value`` with whitespace normalized for storage.

    The transformation is deterministic:

    - Trailing horizontal whitespace on each line is removed.
    - Runs of horizontal whitespace within a line are collapsed to a
      single space.
    - Runs of three or more consecutive newlines are collapsed to two.
    - Leading and trailing newlines are removed.
    """
    without_trailing = _TRAILING_WHITESPACE.sub("", value)
    collapsed = _WHITESPACE_RUN.sub(" ", without_trailing)
    without_excess = _EXCESS_BLANK_LINES.sub("\n\n", collapsed)
    return without_excess.strip()


def _sanitize_metadata(metadata: dict) -> dict[str, str]:
    """Return a normalized copy of the PDF metadata dictionary."""
    result: dict[str, str] = {}
    for key, value in metadata.items():
        if value is None:
            continue
        text = str(value).strip()
        if not text:
            continue
        result[str(key)] = text
    return result


def _sanitize_outline(
    outline: list,
) -> tuple[tuple[int, str, int], ...]:
    """Return the PDF outline as ``(level, title, page_number)`` tuples."""
    result: list[tuple[int, str, int]] = []
    for entry in outline:
        if not isinstance(entry, (list, tuple)) or len(entry) < 3:
            continue
        level = entry[0]
        title = entry[1]
        page_number = entry[2]
        try:
            level_int = int(level)
            page_int = int(page_number)
        except (TypeError, ValueError):
            continue
        if not isinstance(title, str):
            continue
        cleaned = title.strip()
        if not cleaned:
            continue
        result.append((level_int, cleaned, page_int))
    return tuple(result)


def _iso_from_pdf_date(value: str) -> str:
    """Best-effort conversion of a PDF date string to ISO-8601."""
    if not value:
        return ""
    # PDF dates have the form D:YYYYMMDDHHmmSSOHH'mm'.
    text = value.strip()
    if text.startswith("D:"):
        text = text[2:]
    digits = "".join(character for character in text if character.isdigit())
    if len(digits) < 4:
        return ""
    year = digits[0:4]
    month = digits[4:6] if len(digits) >= 6 else "01"
    day = digits[6:8] if len(digits) >= 8 else "01"
    hour = digits[8:10] if len(digits) >= 10 else "00"
    minute = digits[10:12] if len(digits) >= 12 else "00"
    second = digits[12:14] if len(digits) >= 14 else "00"
    try:
        parsed = dt.datetime(
            int(year),
            int(month),
            int(day),
            int(hour),
            int(minute),
            int(second),
        )
    except ValueError:
        return ""
    return parsed.isoformat()