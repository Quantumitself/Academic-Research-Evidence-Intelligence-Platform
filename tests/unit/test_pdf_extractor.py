"""Tests for the PDF text extractor.

The tests build small PDF files with PyMuPDF at test time. They do not
rely on external fixtures, and they do not exercise the network.
"""

from __future__ import annotations

import pytest

import fitz  # PyMuPDF

from academic_platform.infrastructure.document_processing.errors import (
    PdfEncryptedError,
    PdfExtractionError,
    PdfMissingError,
    PdfNotReadableError,
    PdfUnsupportedError,
)
from academic_platform.infrastructure.document_processing.pdf_extractor import (
    PdfExtractionResult,
    PdfExtractorConfig,
    PdfTextExtractor,
)


def _make_pdf(path, pages: list[str]) -> None:
    document = fitz.open()
    try:
        for text in pages:
            page = document.new_page()
            if text:
                page.insert_text((72, 72), text)
        document.set_metadata(
            {
                "title": "Test Document",
                "author": "A. Author; B. Author",
                "subject": "A subject",
                "keywords": "one, two",
                "producer": "Test Producer",
                "creator": "Test Creator",
            }
        )
        document.save(str(path))
    finally:
        document.close()


def test_extract_single_page(tmp_path) -> None:
    path = tmp_path / "single.pdf"
    _make_pdf(path, ["Hello world."])
    extractor = PdfTextExtractor()
    result = extractor.extract(path)
    assert isinstance(result, PdfExtractionResult)
    assert result.page_count == 1
    assert result.extracted_page_count == 1
    assert "Hello world." in result.full_text


def test_extract_multi_page(tmp_path) -> None:
    path = tmp_path / "multi.pdf"
    _make_pdf(path, ["First page.", "Second page.", "Third page."])
    extractor = PdfTextExtractor()
    result = extractor.extract(path)
    assert result.page_count == 3
    assert [page.page_number for page in result.pages] == [1, 2, 3]
    assert "First page." in result.pages[0].text
    assert "Third page." in result.pages[2].text


def test_extract_metadata(tmp_path) -> None:
    path = tmp_path / "meta.pdf"
    _make_pdf(path, ["text"])
    result = PdfTextExtractor().extract(path)
    assert result.metadata.get("title") == "Test Document"
    assert result.metadata.get("author") == "A. Author; B. Author"
    assert result.metadata.get("producer") == "Test Producer"


def test_extract_blocks(tmp_path) -> None:
    path = tmp_path / "blocks.pdf"
    _make_pdf(path, ["Block content."])
    result = PdfTextExtractor().extract(path)
    page = result.pages[0]
    assert page.blocks
    for block in page.blocks:
        assert block.x1 >= block.x0
        assert block.y1 >= block.y0


def test_extract_missing_file(tmp_path) -> None:
    with pytest.raises(PdfMissingError):
        PdfTextExtractor().extract(tmp_path / "missing.pdf")


def test_extract_rejects_non_pdf(tmp_path) -> None:
    path = tmp_path / "not-a-pdf.pdf"
    path.write_bytes(b"not a pdf")
    with pytest.raises((PdfUnsupportedError, PdfNotReadableError)):
        PdfTextExtractor().extract(path)


def test_extract_rejects_directory(tmp_path) -> None:
    directory = tmp_path / "dir.pdf"
    directory.mkdir()
    with pytest.raises(PdfUnsupportedError):
        PdfTextExtractor().extract(directory)


def test_max_pages_truncates(tmp_path) -> None:
    path = tmp_path / "long.pdf"
    _make_pdf(path, ["a", "b", "c", "d", "e"])
    extractor = PdfTextExtractor(PdfExtractorConfig(max_pages=2))
    result = extractor.extract(path)
    assert result.page_count == 5
    assert result.extracted_page_count == 2
    assert result.truncated is True


def test_max_text_bytes_truncates(tmp_path) -> None:
    path = tmp_path / "long.pdf"
    _make_pdf(
        path,
        [
            "first " * 500,
            "second " * 500,
            "third " * 500,
        ],
    )
    extractor = PdfTextExtractor(PdfExtractorConfig(max_text_bytes=200))
    result = extractor.extract(path)
    assert result.truncated is True
    assert result.total_text_bytes <= 400  # one page's worth under the limit
    

def test_strict_mode_raises(tmp_path) -> None:
    # Force a page-level error by monkeypatching the extractor's internal
    # call. We use a small helper to trigger the strict branch without
    # relying on a genuinely corrupted PDF.
    path = tmp_path / "strict.pdf"
    _make_pdf(path, ["text"])
    extractor = PdfTextExtractor(PdfExtractorConfig(strict=True))

    import fitz as _fitz

    original = _fitz.Document.load_page

    def _boom(self, *args, **kwargs):
        raise RuntimeError("simulated failure")

    _fitz.Document.load_page = _boom  # type: ignore[assignment]
    try:
        with pytest.raises(PdfExtractionError):
            extractor.extract(path)
    finally:
        _fitz.Document.load_page = original  # type: ignore[assignment]


def test_non_strict_records_warning(tmp_path) -> None:
    path = tmp_path / "warn.pdf"
    _make_pdf(path, ["text"])
    extractor = PdfTextExtractor(PdfExtractorConfig(strict=False))

    import fitz as _fitz

    original = _fitz.Document.load_page

    def _boom(self, *args, **kwargs):
        raise RuntimeError("simulated failure")

    _fitz.Document.load_page = _boom  # type: ignore[assignment]
    try:
        result = extractor.extract(path)
    finally:
        _fitz.Document.load_page = original  # type: ignore[assignment]
    assert result.warnings
    assert result.extracted_page_count == 0


def test_whitespace_normalization() -> None:
    from academic_platform.infrastructure.document_processing.pdf_extractor import (
        _normalize_whitespace,
    )

    assert _normalize_whitespace("a   b\tc") == "a b c"
    assert _normalize_whitespace("a\n\n\n\nb") == "a\n\nb"
    assert _normalize_whitespace("  \n\n  text  \n") == "text"


def test_extractor_does_not_modify_file(tmp_path) -> None:
    path = tmp_path / "immutable.pdf"
    _make_pdf(path, ["text"])
    before = path.read_bytes()
    PdfTextExtractor().extract(path)
    after = path.read_bytes()
    assert before == after