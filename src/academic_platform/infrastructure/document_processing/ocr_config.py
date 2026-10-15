"""Immutable configuration for the OCR subsystem.

The configuration describes how the OCR pipeline behaves: which pages
it processes, at what resolution, with which languages and Tesseract
parameters, and whether it runs in strict mode. It is frozen so that
its behavior cannot be changed after construction.

Design decisions
----------------
- The page limit is explicit. OCR is expensive; a document with
  hundreds of pages is processed incrementally and the pipeline records
  which pages were processed.
- The resolution is expressed in DPI. The default of 300 DPI matches
  Tesseract's recommended input for printed text; higher values increase
  cost without improving accuracy for most documents.
- Language codes follow Tesseract's three-letter convention
  (``eng``, ``deu``, ``fra``, ...). The default is English.
- The Tesseract configuration string is passed through unchanged.
  Callers that need specific page segmentation modes supply the value
  here; the pipeline never invents parameters.
- The minimum characters threshold is used by the pipeline to decide
  whether a page's extracted text is meaningful. A page that produces
  fewer characters than the threshold is treated as empty.
"""

from __future__ import annotations

from dataclasses import dataclass, field

_DEFAULT_DPI = 300
_DEFAULT_LANGUAGE = "eng"
_DEFAULT_MIN_CHARACTERS = 16


@dataclass(frozen=True, slots=True)
class OcrConfig:
    """Immutable configuration for the OCR pipeline."""

    language: str = _DEFAULT_LANGUAGE
    dpi: int = _DEFAULT_DPI
    tesseract_config: str = ""
    min_characters_per_page: int = _DEFAULT_MIN_CHARACTERS
    max_pages: int | None = None
    timeout_seconds: float = 60.0
    strict: bool = False
    preserve_blocks: bool = True
    languages: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.language or not isinstance(self.language, str):
            raise ValueError("language must be a non-empty string")
        if self.dpi < 70 or self.dpi > 1200:
            raise ValueError("dpi must be between 70 and 1200")
        if self.min_characters_per_page < 1:
            raise ValueError("min_characters_per_page must be at least 1")
        if self.max_pages is not None and self.max_pages < 1:
            raise ValueError("max_pages must be at least 1 when provided")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")

    @property
    def tesseract_language(self) -> str:
        """Return the language string passed to Tesseract.

        When ``languages`` is non-empty, its entries are joined with
        ``+`` so that Tesseract treats them as a combined language set.
        Otherwise ``language`` is used directly.
        """
        if self.languages:
            return "+".join(self.languages)
        return self.language