"""Tests for the PDF metadata extractor.

The tests build small PDFs with PyMuPDF at test time. They do not rely
on external fixtures and do not exercise the network.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import fitz  # PyMuPDF

from academic_platform.infrastructure.document_processing.metadata_extractor import (
    PdfMetadataExtractor,
    extract_arxiv_identifier,
)
from academic_platform.infrastructure.document_processing.pdf_extractor import (
    PdfTextExtractor,
)


def _make_pdf(
    path: Path,
    *,
    body_lines: list[str] | None = None,
    metadata: dict[str, str] | None = None,
) -> None:
    document = fitz.open()
    try:
        page = document.new_page()
        y = 72.0
        for line in body_lines or []:
            page.insert_text((72, y), line)
            y += 16
        if metadata is not None:
            document.set_metadata(metadata)
        document.save(str(path))
    finally:
        document.close()


def test_extract_title_from_embedded(tmp_path: Path) -> None:
    path = tmp_path / "paper.pdf"
    _make_pdf(
        path,
        body_lines=["Introduction"],
        metadata={"title": "A Study of Things"},
    )
    result = PdfMetadataExtractor().extract_from_path(path)
    assert result.title == "A Study of Things"
    assert result.confidence.title >= 0.8


def test_extract_title_from_front_matter(tmp_path: Path) -> None:
    path = tmp_path / "paper.pdf"
    _make_pdf(
        path,
        body_lines=[
            "A Study of Things",
            "A. Author, B. Author",
            "",
            "Abstract",
            "We present a study.",
        ],
    )
    result = PdfMetadataExtractor().extract_from_path(path)
    assert result.title == "A Study of Things"
    assert result.confidence.title > 0.0


def test_placeholder_title_rejected(tmp_path: Path) -> None:
    path = tmp_path / "paper.pdf"
    _make_pdf(
        path,
        body_lines=[
            "A Study of Things",
        ],
        metadata={"title": "Microsoft Word - paper.doc"},
    )
    result = PdfMetadataExtractor().extract_from_path(path)
    assert result.title == "A Study of Things"


def test_extract_authors_from_embedded(tmp_path: Path) -> None:
    path = tmp_path / "paper.pdf"
    _make_pdf(
        path,
        body_lines=["Title"],
        metadata={"author": "A. Author; B. Author"},
    )
    result = PdfMetadataExtractor().extract_from_path(path)
    assert result.authors == ("A. Author", "B. Author")
    assert result.confidence.authors >= 0.8


def test_extract_authors_from_front_matter(tmp_path: Path) -> None:
    path = tmp_path / "paper.pdf"
    _make_pdf(
        path,
        body_lines=[
            "A Study of Things",
            "A. Author and B. Author",
        ],
    )
    result = PdfMetadataExtractor().extract_from_path(path)
    assert "A. Author" in result.authors


def test_institution_rejected_from_authors(tmp_path: Path) -> None:
    path = tmp_path / "paper.pdf"
    _make_pdf(
        path,
        body_lines=["A Study"],
        metadata={"author": "Example University"},
    )
    result = PdfMetadataExtractor().extract_from_path(path)
    assert result.authors == ()


def test_extract_year_from_embedded(tmp_path: Path) -> None:
    path = tmp_path / "paper.pdf"
    _make_pdf(
        path,
        body_lines=["text"],
        metadata={"creationDate": "D:20200101120000Z"},
    )
    result = PdfMetadataExtractor().extract_from_path(path)
    assert result.year == 2020


def test_extract_year_from_front_matter(tmp_path: Path) -> None:
    path = tmp_path / "paper.pdf"
    _make_pdf(
        path,
        body_lines=["A Study", "Published 2019."],
    )
    result = PdfMetadataExtractor().extract_from_path(path)
    assert result.year == 2019


def test_extract_doi_from_front_matter(tmp_path: Path) -> None:
    path = tmp_path / "paper.pdf"
    _make_pdf(
        path,
        body_lines=[
            "A Study",
            "DOI: 10.1000/XYZ.123",
        ],
    )
    result = PdfMetadataExtractor().extract_from_path(path)
    assert result.doi == "10.1000/xyz.123"


def test_extract_arxiv_identifier() -> None:
    text = "Preprint arXiv:2401.12345v2 submitted."
    assert extract_arxiv_identifier(text) == "2401.12345v2"


def test_extract_arxiv_identifier_missing() -> None:
    assert extract_arxiv_identifier("No identifier here.") is None


def test_extract_venue_from_subject(tmp_path: Path) -> None:
    path = tmp_path / "paper.pdf"
    _make_pdf(
        path,
        body_lines=["Title"],
        metadata={"subject": "Journal of Things 2020"},
    )
    result = PdfMetadataExtractor().extract_from_path(path)
    assert result.venue == "Journal of Things 2020"


def test_extract_abstract(tmp_path: Path) -> None:
    path = tmp_path / "paper.pdf"
    _make_pdf(
        path,
        body_lines=[
            "Title",
            "Author",
            "",
            "Abstract",
            "We present a study of things and report results.",
            "",
            "Introduction",
            "The field has developed.",
        ],
    )
    result = PdfMetadataExtractor().extract_from_path(path)
    assert result.abstract is not None
    assert "study of things" in result.abstract
    assert "field has developed" not in result.abstract


def test_extract_language_from_embedded() -> None:
    from pathlib import Path

    from academic_platform.infrastructure.document_processing.pdf_extractor import (
        PdfExtractionResult,
        PdfPageExtraction,
    )

    result = PdfExtractionResult(
        path=Path("/tmp/paper.pdf"),
        page_count=1,
        extracted_page_count=1,
        metadata={"language": "en-US"},
        outline=(),
        pages=(PdfPageExtraction(page_number=1, text="text"),),
        truncated=False,
    )
    extraction = PdfMetadataExtractor().extract_from_result(result)
    assert extraction.language == "en-us"


def test_extract_language_absent(tmp_path: Path) -> None:
    path = tmp_path / "paper.pdf"
    _make_pdf(path, body_lines=["text"])
    result = PdfMetadataExtractor().extract_from_path(path)
    assert result.language is None


def test_field_count(tmp_path: Path) -> None:
    from pathlib import Path

    from academic_platform.infrastructure.document_processing.pdf_extractor import (
        PdfExtractionResult,
        PdfPageExtraction,
    )

    result = PdfExtractionResult(
        path=Path("/tmp/paper.pdf"),
        page_count=1,
        extracted_page_count=1,
        metadata={
            "title": "A Study",
            "author": "A. Author",
            "creationDate": "D:20200101120000Z",
        },
        outline=(),
        pages=(PdfPageExtraction(page_number=1, text="text"),),
        truncated=False,
    )
    extraction = PdfMetadataExtractor().extract_from_result(result)
    assert extraction.field_count() >= 3


def test_deterministic(tmp_path: Path) -> None:
    path = tmp_path / "paper.pdf"
    _make_pdf(
        path,
        body_lines=["A Study", "Author A"],
    )
    extractor = PdfMetadataExtractor()
    first = extractor.extract_from_path(path)
    second = extractor.extract_from_path(path)
    assert first.title == second.title
    assert first.authors == second.authors
    assert first.doi == second.doi