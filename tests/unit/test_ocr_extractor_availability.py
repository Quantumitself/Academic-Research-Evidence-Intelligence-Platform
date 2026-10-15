"""Tests for the OCR availability probe.

The tests do not require a live Tesseract binary. They monkeypatch the
``pytesseract`` import to exercise both the missing-dependency and
missing-binary branches.
"""

from __future__ import annotations

import builtins
import sys

import pytest

from academic_platform.infrastructure.document_processing.ocr_extractor import (
    OcrAvailability,
    PdfOcrExtractor,
)


def test_probe_reports_unavailable_when_wrapper_missing(monkeypatch) -> None:
    # Force the import of ``pytesseract`` to fail.
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "pytesseract":
            raise ImportError("simulated missing module")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    result = PdfOcrExtractor().probe_availability()
    assert isinstance(result, OcrAvailability)
    assert result.available is False
    assert "pytesseract" in result.message.lower()


def test_probe_reports_unavailable_when_binary_missing(monkeypatch) -> None:
    # Provide a fake pytesseract module whose version call fails.
    class _FakePytesseract:
        Output = type("Output", (), {"DICT": "dict"})

        @staticmethod
        def get_tesseract_version():
            raise RuntimeError("tesseract not found")

        @staticmethod
        def get_languages(config=""):
            return []

    fake_module = _FakePytesseract()
    monkeypatch.setitem(sys.modules, "pytesseract", fake_module)
    result = PdfOcrExtractor().probe_availability()
    assert result.available is False
    assert "Tesseract binary" in result.message


def test_probe_reports_available_with_languages(monkeypatch) -> None:
    class _FakePytesseract:
        Output = type("Output", (), {"DICT": "dict"})

        @staticmethod
        def get_tesseract_version():
            return "5.3.0"

        @staticmethod
        def get_languages(config=""):
            return ["eng", "deu"]

    monkeypatch.setitem(sys.modules, "pytesseract", _FakePytesseract())
    result = PdfOcrExtractor().probe_availability()
    assert result.available is True
    assert result.tesseract_version == "5.3.0"
    assert "eng" in result.languages
    assert "deu" in result.languages