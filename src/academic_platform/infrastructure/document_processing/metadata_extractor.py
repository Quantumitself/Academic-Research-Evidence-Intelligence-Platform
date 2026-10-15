"""Bibliographic metadata extraction from PDFs.

The extractor combines three sources of evidence:

1. The PDF's embedded metadata dictionary (title, author, subject,
   keywords, producer, creation date).
2. The first page's text, which frequently carries the title, author
   list, and abstract in a scholarly paper.
3. Pattern matching over the front-matter text for a DOI, an arXiv
   identifier, a year, and a venue.

Each field is produced with a confidence value in ``[0.0, 1.0]``. The
confidence reflects how much the extractor trusts the evidence: fields
taken from the embedded metadata dictionary carry a higher confidence
than fields inferred from the first page.

Design decisions
----------------
- The extractor never invents values. Fields that cannot be extracted
  are left ``None`` and their confidence is 0.0.
- The extractor never overwrites the PDF. It reads the file and, when a
  PyMuPDF document handle is already available, reuses it.
- The extractor is deterministic: the same PDF produces the same
  result on every run.
- The extractor operates on a ``PdfExtractionResult`` when one is
  available. When the caller only has a path, the extractor runs the
  PDF text extractor itself for the pages it needs.
- Author parsing accepts three common separators: semicolons, "and",
  and comma-separated lists with a trailing "and". It rejects strings
  that do not look like author lists.
- The DOI pattern matches the canonical ``10.<registrant>/<suffix>``
  form. arXiv identifiers match the ``arXiv:YYMM.NNNNN`` form.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

from academic_platform.infrastructure.document_processing.errors import (
    DocumentProcessingError,
)
from academic_platform.infrastructure.document_processing.pdf_extractor import (
    PdfExtractionResult,
    PdfTextExtractor,
)

_logger = logging.getLogger(__name__)


# DOI pattern: "10." followed by a four-or-more digit registrant, a
# slash, and a suffix of allowed characters. Case-insensitive.
_DOI_PATTERN = re.compile(
    r"\b10\.\d{4,9}/[-._;()/:A-Z0-9]+",
    re.IGNORECASE,
)

# arXiv identifier as it appears in front matter.
_ARXIV_PATTERN = re.compile(
    r"\barXiv:\s*(\d{4}\.\d{4,5})(v\d+)?",
    re.IGNORECASE,
)

# Four-digit year between 1800 and 2099, bounded by non-digits.
_YEAR_PATTERN = re.compile(r"\b(1[89]\d{2}|20\d{2})\b")

# Title candidates: a line of at least eight characters, mostly
# alphabetic, without terminal punctuation typical of a running head.
_TITLE_LINE_MIN_LENGTH = 8
_TITLE_LINE_MAX_LENGTH = 300

# Author line heuristics.
_AUTHOR_LINE_MAX_LENGTH = 400

# Abstract markers commonly found in scholarly PDFs.
_ABSTRACT_MARKER = re.compile(
    r"^\s*(abstract|summary)\b[\s:.\-]*",
    re.IGNORECASE | re.MULTILINE,
)


@dataclass(frozen=True, slots=True)
class FieldConfidence:
    """Confidence values for each extracted field."""

    title: float = 0.0
    authors: float = 0.0
    year: float = 0.0
    venue: float = 0.0
    doi: float = 0.0
    abstract: float = 0.0
    language: float = 0.0


@dataclass(frozen=True, slots=True)
class PdfMetadataExtraction:
    """Result of extracting bibliographic metadata from a PDF."""

    path: Path
    title: str | None = None
    authors: tuple[str, ...] = field(default_factory=tuple)
    year: int | None = None
    venue: str | None = None
    doi: str | None = None
    abstract: str | None = None
    language: str | None = None
    confidence: FieldConfidence = field(default_factory=FieldConfidence)

    @property
    def has_title(self) -> bool:
        return bool(self.title)

    @property
    def has_authors(self) -> bool:
        return bool(self.authors)

    @property
    def is_minimal(self) -> bool:
        """Return True when only a title was extracted."""
        return bool(self.title) and not self.authors

    def field_count(self) -> int:
        """Return the number of fields that were successfully extracted."""
        count = 0
        if self.title:
            count += 1
        if self.authors:
            count += 1
        if self.year is not None:
            count += 1
        if self.venue:
            count += 1
        if self.doi:
            count += 1
        if self.abstract:
            count += 1
        if self.language:
            count += 1
        return count


class PdfMetadataExtractor:
    """Extract bibliographic metadata from a PDF by heuristic analysis."""

    def __init__(
        self,
        *,
        text_extractor: PdfTextExtractor | None = None,
        max_front_matter_pages: int = 3,
    ) -> None:
        if max_front_matter_pages < 1:
            raise ValueError("max_front_matter_pages must be at least 1")
        self._text_extractor = text_extractor or PdfTextExtractor()
        self._max_front_matter_pages = max_front_matter_pages

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def extract_from_path(self, path: Path) -> PdfMetadataExtraction:
        """Extract metadata by reading the PDF at ``path``.

        Raises
        ------
        DocumentProcessingError
            If the PDF cannot be opened.
        """
        result = self._text_extractor.extract(path)
        return self.extract_from_result(result)

    def extract_from_result(
        self,
        result: PdfExtractionResult,
    ) -> PdfMetadataExtraction:
        """Extract metadata from an already-extracted PDF result."""
        embedded = _normalize_embedded_metadata(result.metadata)
        front_matter = _collect_front_matter(result, self._max_front_matter_pages)

        title, title_confidence = _extract_title(embedded, front_matter)
        authors, authors_confidence = _extract_authors(embedded, front_matter)
        year, year_confidence = _extract_year(embedded, front_matter)
        venue, venue_confidence = _extract_venue(embedded, front_matter)
        doi, doi_confidence = _extract_doi(front_matter)
        abstract, abstract_confidence = _extract_abstract(front_matter)
        language, language_confidence = _extract_language(embedded)

        return PdfMetadataExtraction(
            path=result.path,
            title=title,
            authors=authors,
            year=year,
            venue=venue,
            doi=doi,
            abstract=abstract,
            language=language,
            confidence=FieldConfidence(
                title=title_confidence,
                authors=authors_confidence,
                year=year_confidence,
                venue=venue_confidence,
                doi=doi_confidence,
                abstract=abstract_confidence,
                language=language_confidence,
            ),
        )


# ----------------------------------------------------------------------
# Embedded metadata
# ----------------------------------------------------------------------
def _normalize_embedded_metadata(metadata: dict) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for key, value in metadata.items():
        if not isinstance(key, str):
            continue
        if not isinstance(value, str):
            continue
        cleaned = value.strip()
        if not cleaned:
            continue
        # Some producers write placeholder strings such as "untitled"
        # or "Microsoft Word - paper.doc" into the title field. The
        # extractor rejects those outright.
        if key.lower() == "title" and _is_placeholder_title(cleaned):
            continue
        normalized[key.lower()] = cleaned
    return normalized


def _is_placeholder_title(value: str) -> bool:
    lowered = value.strip().lower()
    if lowered in {"untitled", "document1", "microsoft word", "paper", "article"}:
        return True
    if lowered.startswith("microsoft word - ") and lowered.endswith(".doc"):
        return True
    if lowered.endswith(".doc") or lowered.endswith(".docx"):
        return True
    if lowered.endswith(".pdf"):
        return True
    if lowered.endswith(".tex") or lowered.endswith(".dvi"):
        return True
    return False


# ----------------------------------------------------------------------
# Front matter collection
# ----------------------------------------------------------------------
def _collect_front_matter(
    result: PdfExtractionResult,
    max_pages: int,
) -> str:
    parts: list[str] = []
    for page in result.pages[:max_pages]:
        if page.text:
            parts.append(page.text)
    return "\n\n".join(parts).strip()


# ----------------------------------------------------------------------
# Title
# ----------------------------------------------------------------------
def _extract_title(
    embedded: dict[str, str],
    front_matter: str,
) -> tuple[str | None, float]:
    embedded_title = embedded.get("title")
    if embedded_title and _looks_like_title(embedded_title):
        return embedded_title, 0.9
    from_text = _title_from_front_matter(front_matter)
    if from_text:
        return from_text, 0.6
    if embedded_title:
        return embedded_title, 0.4
    return None, 0.0


def _looks_like_title(value: str) -> bool:
    stripped = value.strip()
    if len(stripped) < _TITLE_LINE_MIN_LENGTH:
        return False
    if len(stripped) > _TITLE_LINE_MAX_LENGTH:
        return False
    if stripped.isupper() and len(stripped) < 12:
        return False
    return True


def _title_from_front_matter(front_matter: str) -> str | None:
    if not front_matter:
        return None
    lines = [line.strip() for line in front_matter.splitlines()]
    candidates: list[tuple[int, str]] = []
    for index, line in enumerate(lines[:60]):
        if not line:
            continue
        if _is_candidate_title_line(line):
            candidates.append((index, line))
    if not candidates:
        return None
    # The earliest line that looks like a title wins; among equally
    # early candidates the longest is preferred.
    earliest = candidates[0][0]
    same_position = [c for c in candidates if c[0] == earliest]
    same_position.sort(key=lambda item: -len(item[1]))
    return same_position[0][1]


def _is_candidate_title_line(line: str) -> bool:
    if len(line) < _TITLE_LINE_MIN_LENGTH or len(line) > _TITLE_LINE_MAX_LENGTH:
        return False
    stripped = line.strip()
    if stripped.endswith(":"):
        return False
    if stripped.endswith("."):
        return False
    # Reject running heads and page markers.
    if re.match(r"^\d+\s", stripped):
        return False
    if re.match(r"^page\s+\d+", stripped, re.IGNORECASE):
        return False
    if re.match(r"^https?://", stripped):
        return False
    if _is_email_line(stripped):
        return False
    letters = sum(1 for character in stripped if character.isalpha())
    if letters < len(stripped) * 0.5:
        return False
    return True


def _is_email_line(value: str) -> bool:
    return "@" in value and "." in value


# ----------------------------------------------------------------------
# Authors
# ----------------------------------------------------------------------
def _extract_authors(
    embedded: dict[str, str],
    front_matter: str,
) -> tuple[tuple[str, ...], float]:
    embedded_author = embedded.get("author")
    if embedded_author:
        parsed = _parse_author_string(embedded_author)
        if parsed:
            return parsed, 0.85
    from_text = _authors_from_front_matter(front_matter)
    if from_text:
        return from_text, 0.5
    return (), 0.0


_AUTHOR_SEPARATOR = re.compile(r"\s*(?:;|,|\band\b)\s*", re.IGNORECASE)


def _parse_author_string(value: str) -> tuple[str, ...]:
    cleaned = value.strip()
    if not cleaned or len(cleaned) > _AUTHOR_LINE_MAX_LENGTH:
        return ()
    # Reject entries that look like an institution rather than a person.
    if "@" in cleaned or "http" in cleaned.lower():
        return ()
    parts = [part.strip() for part in _AUTHOR_SEPARATOR.split(cleaned) if part.strip()]
    results: list[str] = []
    for part in parts:
        normalized = _normalize_author_token(part)
        if normalized:
            results.append(normalized)
    return tuple(results)


def _normalize_author_token(value: str) -> str | None:
    token = value.strip().strip(",;")
    if not token:
        return None
    if len(token) > 120:
        return None
    # A person's name has at least two alphabetic characters.
    letters = sum(1 for character in token if character.isalpha())
    if letters < 2:
        return None
    # Reject tokens that carry typical non-author markers.
    lowered = token.lower()
    if any(
        marker in lowered
        for marker in ("university", "institute", "department", "school")
    ):
        return None
    return token


def _authors_from_front_matter(front_matter: str) -> tuple[str, ...]:
    if not front_matter:
        return ()
    lines = [line.strip() for line in front_matter.splitlines()]
    for line in lines[:40]:
        if len(line) < 6 or len(line) > _AUTHOR_LINE_MAX_LENGTH:
            continue
        if "@" in line:
            continue
        if not _looks_like_author_line(line):
            continue
        parsed = _parse_author_string(line)
        if len(parsed) >= 1:
            return parsed
    return ()


def _looks_like_author_line(line: str) -> bool:
    # Author lines usually contain at least one separator or two
    # capitalized names.
    if ";" in line or " and " in line.lower() or line.count(",") >= 1:
        capitalized = re.findall(r"\b[A-Z][a-z]+\b", line)
        return len(capitalized) >= 2
    return False


# ----------------------------------------------------------------------
# Year
# ----------------------------------------------------------------------
def _extract_year(
    embedded: dict[str, str],
    front_matter: str,
) -> tuple[int | None, float]:
    creation = embedded.get("creationdate") or embedded.get("moddate")
    if creation:
        candidate = _year_from_pdf_date(creation)
        if candidate is not None:
            return candidate, 0.7
    from_text = _year_from_front_matter(front_matter)
    if from_text is not None:
        return from_text, 0.5
    return None, 0.0


def _year_from_pdf_date(value: str) -> int | None:
    """Return the year embedded in a PDF date string.

    PDF dates have the form ``D:YYYYMMDDHHmmSSOHH'mm'``. The year is the
    first four digits after the optional ``D:`` prefix. The helper does
    not use the general year pattern because the digits are not
    surrounded by word boundaries.
    """
    text = value.strip()
    if text.startswith("D:"):
        text = text[2:]
    digits = "".join(character for character in text if character.isdigit())
    if len(digits) < 4:
        return None
    year_text = digits[:4]
    try:
        year = int(year_text)
    except ValueError:
        return None
    if year < 1800 or year > 2099:
        return None
    return year


def _year_from_front_matter(front_matter: str) -> int | None:
    if not front_matter:
        return None
    candidates: list[int] = []
    for match in _YEAR_PATTERN.finditer(front_matter[:2000]):
        try:
            candidates.append(int(match.group(1)))
        except ValueError:
            continue
    if not candidates:
        return None
    # Prefer the highest year; the copyright line usually carries the
    # most recent year.
    return max(candidates)


# ----------------------------------------------------------------------
# Venue
# ----------------------------------------------------------------------
def _extract_venue(
    embedded: dict[str, str],
    front_matter: str,
) -> tuple[str | None, float]:
    subject = embedded.get("subject")
    if subject and len(subject) <= 200:
        lowered = subject.lower()
        if "journal" in lowered or "conference" in lowered or "proceedings" in lowered:
            return subject, 0.5
    from_text = _venue_from_front_matter(front_matter)
    if from_text:
        return from_text, 0.4
    return None, 0.0


_VENUE_LINE_PATTERN = re.compile(
    r"\b(?:proceedings|journal|conference|workshop|symposium)\b",
    re.IGNORECASE,
)


def _venue_from_front_matter(front_matter: str) -> str | None:
    if not front_matter:
        return None
    lines = [line.strip() for line in front_matter.splitlines()]
    for line in lines[:40]:
        if not line:
            continue
        if len(line) > 200:
            continue
        if _VENUE_LINE_PATTERN.search(line):
            return line
    return None


# ----------------------------------------------------------------------
# DOI and arXiv identifier
# ----------------------------------------------------------------------
def _extract_doi(front_matter: str) -> tuple[str | None, float]:
    if not front_matter:
        return None, 0.0
    match = _DOI_PATTERN.search(front_matter)
    if not match:
        return None, 0.0
    return match.group(0).rstrip(".,;:").lower(), 0.85


def extract_arxiv_identifier(text: str) -> str | None:
    """Return the arXiv identifier found in ``text``, or ``None``.

    Exposed for callers that want to inspect the front matter for an
    arXiv identifier independently of the metadata extraction.
    """
    if not text:
        return None
    match = _ARXIV_PATTERN.search(text)
    if not match:
        return None
    identifier = match.group(1)
    version = match.group(2) or ""
    return f"{identifier}{version}"


# ----------------------------------------------------------------------
# Abstract
# ----------------------------------------------------------------------
def _extract_abstract(front_matter: str) -> tuple[str | None, float]:
    if not front_matter:
        return None, 0.0
    match = _ABSTRACT_MARKER.search(front_matter)
    if not match:
        return None, 0.0
    start = match.end()
    remainder = front_matter[start:].strip()
    if not remainder:
        return None, 0.0
    # The abstract ends at the first blank-line-separated paragraph
    # boundary, or at the first paragraph that starts with a common
    # section marker.
    cutoff_markers = (
        "introduction",
        "keywords",
        "1.",
        "i.",
        "background",
        "methods",
    )
    # The front matter produced by the PDF extractor joins lines with a
    # single newline and paragraphs with a blank line. Both boundaries
    # are respected: a blank line ends the abstract, and a line whose
    # stripped content begins with a section marker also ends it.
    collected: list[str] = []
    paragraph_lines: list[str] = []
    for raw_line in remainder.splitlines():
        line = raw_line.strip()
        if not line:
            if paragraph_lines:
                collected.append(" ".join(paragraph_lines))
                paragraph_lines = []
            continue
        lowered = line.lower()
        if any(lowered.startswith(marker) for marker in cutoff_markers):
            break
        paragraph_lines.append(line)
        if len(" ".join(collected + paragraph_lines)) > 3000:
            break
    if paragraph_lines:
        collected.append(" ".join(paragraph_lines))
    if not collected:
        return None, 0.0
    abstract = " ".join(collected)
    return abstract, 0.6


# ----------------------------------------------------------------------
# Language
# ----------------------------------------------------------------------
_LANGUAGE_PATTERN = re.compile(r"^[a-z]{2}(?:-[a-zA-Z]{2})?$")


def _extract_language(embedded: dict[str, str]) -> tuple[str | None, float]:
    candidate = embedded.get("language") or embedded.get("lang")
    if not candidate:
        return None, 0.0
    if not _LANGUAGE_PATTERN.match(candidate.strip()):
        return None, 0.0
    return candidate.strip().lower(), 0.9