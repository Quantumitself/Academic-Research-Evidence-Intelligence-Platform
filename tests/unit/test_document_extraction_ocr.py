"""Tests for the OCR integration in the document extraction service."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

import fitz  # PyMuPDF

from academic_platform.application.document_extraction.service import (
    DocumentExtractionService,
    _needs_ocr,
)
from academic_platform.infrastructure.database import Database
from academic_platform.infrastructure.database.base import Base
from academic_platform.infrastructure.database.models import (
    DocumentAsset,
    DocumentChunk,
)
from academic_platform.infrastructure.document_processing.ocr_config import (
    OcrConfig,
)
from academic_platform.infrastructure.document_processing.pdf_extractor import (
    PdfExtractionResult,
    PdfPageExtraction,
)
from academic_platform.infrastructure.repositories.factory import (
    _REPOSITORY_REGISTRY,
)
from academic_platform.infrastructure.repositories.manager import (
    RepositoryManager,
)


@pytest.fixture()
def database() -> Database:
    db = Database.in_memory()
    Base.metadata.create_all(db.engine)
    yield db
    db.dispose()


def _make_scanned_pdf(path: Path) -> None:
    """Build a PDF with no extractable text (an image-only page)."""
    document = fitz.open()
    try:
        page = document.new_page()
        # Draw a filled rectangle; no text is inserted.
        page.draw_rect(fitz.Rect(72, 72, 200, 200), color=(0, 0, 0), fill=(0, 0, 0))
        document.save(str(path))
    finally:
        document.close()


def _seed_document(database: Database, path: Path) -> None:
    with database.session() as session:
        session.add(
            DocumentAsset(
                key="doc-1",
                display_name="Scanned",
                location=str(path.resolve()),
                checksum_sha256="0" * 64,
            )
        )


class _FakePytesseract:
    Output = type("Output", (), {"DICT": "dict"})

    def __init__(self, text: str) -> None:
        self._text = text

    def get_tesseract_version(self):
        return "5.3.0"

    def get_languages(self, config=""):
        return ["eng"]

    def image_to_string(self, image, **kwargs):
        return self._text

    def image_to_data(self, image, **kwargs):
        return {
            "text": [word for word in self._text.split() if word],
            "block_num": [1] * len(self._text.split()),
            "left": [10] * len(self._text.split()),
            "top": [10] * len(self._text.split()),
            "width": [40] * len(self._text.split()),
            "height": [12] * len(self._text.split()),
            "conf": ["95"] * len(self._text.split()),
        }


def test_needs_ocr_when_no_text() -> None:
    result = PdfExtractionResult(
        path=Path("/tmp/x.pdf"),
        page_count=1,
        extracted_page_count=1,
        metadata={},
        outline=(),
        pages=(PdfPageExtraction(page_number=1, text=""),),
        truncated=False,
    )
    assert _needs_ocr(result) is True


def test_needs_ocr_when_tiny_text() -> None:
    result = PdfExtractionResult(
        path=Path("/tmp/x.pdf"),
        page_count=10,
        extracted_page_count=10,
        metadata={},
        outline=(),
        pages=tuple(
            PdfPageExtraction(page_number=i, text="x")
            for i in range(1, 11)
        ),
        truncated=False,
    )
    assert _needs_ocr(result) is True


def test_no_ocr_when_text_present() -> None:
    result = PdfExtractionResult(
        path=Path("/tmp/x.pdf"),
        page_count=1,
        extracted_page_count=1,
        metadata={},
        outline=(),
        pages=(
            PdfPageExtraction(
                page_number=1,
                text="A reasonably long passage of text. " * 3,
            ),
        ),
        truncated=False,
    )
    assert _needs_ocr(result) is False


def test_ocr_runs_when_enabled_and_needed(
    database: Database, tmp_path: Path, monkeypatch
) -> None:
    pdf = tmp_path / "scanned.pdf"
    _make_scanned_pdf(pdf)
    _seed_document(database, pdf)

    monkeypatch.setitem(
        sys.modules, "pytesseract", _FakePytesseract("Hello from OCR.")
    )

    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = DocumentExtractionService(
            repositories,
            ocr_enabled=True,
            ocr_config=OcrConfig(dpi=150),
        )
        outcome = service.extract_document("doc-1")
        assert outcome.chunk_count >= 1

    with database.session() as session:
        row = session.query(DocumentAsset).one()
        assert row.ocr_state == "completed"
        chunks = session.query(DocumentChunk).all()
        assert any("Hello" in chunk.content for chunk in chunks)


def test_ocr_skipped_when_disabled(
    database: Database, tmp_path: Path
) -> None:
    pdf = tmp_path / "scanned.pdf"
    _make_scanned_pdf(pdf)
    _seed_document(database, pdf)
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = DocumentExtractionService(repositories, ocr_enabled=False)
        service.extract_document("doc-1")
    with database.session() as session:
        row = session.query(DocumentAsset).one()
        assert row.ocr_state == "not_required"


def test_ocr_failure_records_state(
    database: Database, tmp_path: Path, monkeypatch
) -> None:
    pdf = tmp_path / "scanned.pdf"
    _make_scanned_pdf(pdf)
    _seed_document(database, pdf)

    class _Unavailable:
        Output = type("Output", (), {"DICT": "dict"})

        @staticmethod
        def get_tesseract_version():
            raise RuntimeError("missing")

        @staticmethod
        def get_languages(config=""):
            return []

    monkeypatch.setitem(sys.modules, "pytesseract", _Unavailable())

    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = DocumentExtractionService(
            repositories, ocr_enabled=True, ocr_config=OcrConfig(dpi=150)
        )
        outcome = service.extract_document("doc-1")
        # The extraction still completes; the OCR warning is reported.
        assert any("Tesseract" in warning for warning in outcome.warnings)

    with database.session() as session:
        row = session.query(DocumentAsset).one()
        assert row.ocr_state == "failed"