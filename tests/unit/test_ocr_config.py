"""Tests for the OCR configuration value object."""

from __future__ import annotations

import pytest

from academic_platform.infrastructure.document_processing.ocr_config import (
    OcrConfig,
)


def test_defaults() -> None:
    config = OcrConfig()
    assert config.language == "eng"
    assert config.dpi == 300
    assert config.min_characters_per_page == 16
    assert config.strict is False
    assert config.preserve_blocks is True


def test_rejects_empty_language() -> None:
    with pytest.raises(ValueError):
        OcrConfig(language="")


def test_rejects_low_dpi() -> None:
    with pytest.raises(ValueError):
        OcrConfig(dpi=50)


def test_rejects_high_dpi() -> None:
    with pytest.raises(ValueError):
        OcrConfig(dpi=2000)


def test_rejects_zero_min_characters() -> None:
    with pytest.raises(ValueError):
        OcrConfig(min_characters_per_page=0)


def test_rejects_zero_max_pages() -> None:
    with pytest.raises(ValueError):
        OcrConfig(max_pages=0)


def test_rejects_zero_timeout() -> None:
    with pytest.raises(ValueError):
        OcrConfig(timeout_seconds=0)


def test_language_uses_languages_when_provided() -> None:
    config = OcrConfig(language="eng", languages=("eng", "deu"))
    assert config.tesseract_language == "eng+deu"


def test_language_uses_single_language_when_languages_empty() -> None:
    config = OcrConfig(language="eng")
    assert config.tesseract_language == "eng"