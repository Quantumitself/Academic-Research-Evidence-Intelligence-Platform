"""Document processing adapters.

This subpackage owns the concrete implementations that turn a document
asset on disk into structured data the application can use:

- PDF text extraction (PyMuPDF).
- Metadata extraction from PDF embedded metadata and front matter.
- Optional OCR for scanned PDFs through Tesseract.

Adapters in this subpackage never import Qt. They raise typed
``DocumentProcessingError`` subclasses.
"""

from academic_platform.infrastructure.document_processing.errors import (
    DocumentProcessingError,
    PdfEncryptedError,
    PdfExtractionError,
    PdfMissingError,
    PdfNotReadableError,
    PdfUnsupportedError,
)
from academic_platform.infrastructure.document_processing.metadata_extractor import (
    FieldConfidence,
    PdfMetadataExtraction,
    PdfMetadataExtractor,
    extract_arxiv_identifier,
)
from academic_platform.infrastructure.document_processing.ocr_config import (
    OcrConfig,
)
from academic_platform.infrastructure.document_processing.ocr_errors import (
    OcrError,
    OcrLanguageError,
    OcrPageError,
    OcrTimeoutError,
    OcrUnavailableError,
)
from academic_platform.infrastructure.document_processing.ocr_extractor import (
    OcrAvailability,
    PdfOcrExtractor,
)
from academic_platform.infrastructure.document_processing.pdf_extractor import (
    PdfExtractionResult,
    PdfExtractorConfig,
    PdfPageExtraction,
    PdfTextBlock,
    PdfTextExtractor,
)

__all__ = [
    "DocumentProcessingError",
    "FieldConfidence",
    "OcrAvailability",
    "OcrConfig",
    "OcrError",
    "OcrLanguageError",
    "OcrPageError",
    "OcrTimeoutError",
    "OcrUnavailableError",
    "PdfEncryptedError",
    "PdfExtractionError",
    "PdfExtractionResult",
    "PdfExtractorConfig",
    "PdfMetadataExtraction",
    "PdfMetadataExtractor",
    "PdfMissingError",
    "PdfNotReadableError",
    "PdfOcrExtractor",
    "PdfPageExtraction",
    "PdfTextBlock",
    "PdfTextExtractor",
    "PdfUnsupportedError",
    "extract_arxiv_identifier",
]
