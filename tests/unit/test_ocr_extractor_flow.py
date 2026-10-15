"""Tests for the OCR extractor's page flow.

The tests inject a fake ``pytesseract`` module and a minimal PDF built
with PyMuPDF. They exercise the composition of rasterization, Tesseract
invocation, block extraction, and error handling.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

import fitz  # PyMuPDF

from academic_platform.infrastructure.document_processing.errors import (
    PdfExtractionError,
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
from academic_platform.infrastructure.document_processing.ocr_extractor import (
    PdfOcrExtractor,
)


class _FakePytesseract:
    Output = type("Output", (), {"DICT": "dict"})

    def __init__(
        self,
        *,
        text: str = "Hello OCR",
        raise_on_string: Exception | None = None,
        raise_on_data: Exception | None = None,
        languages: list[str] | None = None,
    ) -> None:
        self._text = text
        self._raise_on_string = raise_on_string
        self._raise_on_data = raise_on_data
        self._languages = languages or ["eng"]

    def get_tesseract_version(self):
        return "5.3.0"

    def get_languages(self, config=""):
        return list(self._languages)

    def image_to_string(self, image, **kwargs):
        if self._raise_on_string is not None:
            raise self._raise_on_string
        return self._text

    def image_to_data(self, image, **kwargs):
        if self._raise_on_data is not None:
            raise self._raise_on_data
        return {
            "text": ["Hello", "OCR"],
            "block_num": [1, 1],
            "left": [10, 60],
            "top": [10, 10],
            "width": [40, 40],
            "height": [12, 12],
            "conf": ["95", "90"],
        }


def _make_pdf(path: Path) -> None:
    document = fitz.open()
    try:
        page = document.new_page()
        page.insert_text((72, 72), "x")
        document.save(str(path))
    finally:
        document.close()


def test_extract_requires_availability(tmp_path: Path, monkeypatch) -> None:
    # Simulate an unavailable backend.
    class _Unavailable:
        Output = type("Output", (), {"DICT": "dict"})

        @staticmethod
        def get_tesseract_version():
            raise RuntimeError("missing")

        @staticmethod
        def get_languages(config=""):
            return []

    monkeypatch.setitem(sys.modules, "pytesseract", _Unavailable())
    pdf = tmp_path / "paper.pdf"
    _make_pdf(pdf)
    with pytest.raises(OcrUnavailableError):
        PdfOcrExtractor().extract(pdf)


def test_extract_produces_text_and_blocks(tmp_path: Path, monkeypatch) -> None:
    fake = _FakePytesseract(text="Hello OCR world.")
    monkeypatch.setitem(sys.modules, "pytesseract", fake)
    pdf = tmp_path / "paper.pdf"
    _make_pdf(pdf)
    result = PdfOcrExtractor(OcrConfig(dpi=150)).extract(pdf)
    assert result.page_count == 1
    assert result.extracted_page_count == 1
    assert "Hello OCR" in result.pages[0].text
    assert result.pages[0].blocks


def test_extract_disables_blocks_when_configured(tmp_path: Path, monkeypatch) -> None:
    fake = _FakePytesseract(text="Hello OCR world.")
    monkeypatch.setitem(sys.modules, "pytesseract", fake)
    pdf = tmp_path / "paper.pdf"
    _make_pdf(pdf)
    result = PdfOcrExtractor(
        OcrConfig(dpi=150, preserve_blocks=False)
    ).extract(pdf)
    assert result.pages[0].blocks == ()


def test_language_check_rejects_missing_pack(tmp_path: Path, monkeypatch) -> None:
    fake = _FakePytesseract(text="text", languages=["eng"])
    monkeypatch.setitem(sys.modules, "pytesseract", fake)
    pdf = tmp_path / "paper.pdf"
    _make_pdf(pdf)
    with pytest.raises(OcrLanguageError):
        PdfOcrExtractor(OcrConfig(language="deu")).extract(pdf)


def test_timeout_is_translated(tmp_path: Path, monkeypatch) -> None:
    fake = _FakePytesseract(
        raise_on_string=RuntimeError("Tesseract timeout exceeded"),
    )
    monkeypatch.setitem(sys.modules, "pytesseract", fake)
    pdf = tmp_path / "paper.pdf"
    _make_pdf(pdf)
    result = PdfOcrExtractor(OcrConfig(dpi=150)).extract(pdf)
    assert result.pages[0].warning
    assert "timed out" in result.pages[0].warning.lower()


def test_timeout_strict_raises(tmp_path: Path, monkeypatch) -> None:
    fake = _FakePytesseract(
        raise_on_string=RuntimeError("Tesseract timeout exceeded"),
    )
    monkeypatch.setitem(sys.modules, "pytesseract", fake)
    pdf = tmp_path / "paper.pdf"
    _make_pdf(pdf)
    with pytest.raises(PdfExtractionError):
        PdfOcrExtractor(OcrConfig(dpi=150, strict=True)).extract(pdf)


def test_page_error_is_recorded(tmp_path: Path, monkeypatch) -> None:
    fake = _FakePytesseract(raise_on_string=RuntimeError("some failure"))
    monkeypatch.setitem(sys.modules, "pytesseract", fake)
    pdf = tmp_path / "paper.pdf"
    _make_pdf(pdf)
    result = PdfOcrExtractor(OcrConfig(dpi=150)).extract(pdf)
    assert result.pages[0].warning
    assert result.warnings


def test_block_extraction_failure_is_non_fatal(tmp_path: Path, monkeypatch) -> None:
    fake = _FakePytesseract(
        text="Hello OCR world.",
        raise_on_data=RuntimeError("data extraction failed"),
    )
    monkeypatch.setitem(sys.modules, "pytesseract", fake)
    pdf = tmp_path / "paper.pdf"
    _make_pdf(pdf)
    result = PdfOcrExtractor(OcrConfig(dpi=150)).extract(pdf)
    assert result.pages[0].text
    assert result.pages[0].blocks == ()


def test_max_pages_truncates(tmp_path: Path, monkeypatch) -> None:
    fake = _FakePytesseract(text="Hello OCR world.")
    monkeypatch.setitem(sys.modules, "pytesseract", fake)
    pdf = tmp_path / "multi.pdf"
    document = fitz.open()
    try:
        for _ in range(3):
            page = document.new_page()
            page.insert_text((72, 72), "x")
        document.save(str(pdf))
    finally:
        document.close()
    result = PdfOcrExtractor(
        OcrConfig(dpi=150, max_pages=2)
    ).extract(pdf)
    assert result.page_count == 3
    assert result.extracted_page_count == 2
    assert result.truncated is True