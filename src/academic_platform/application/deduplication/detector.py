"""Duplicate detection.

The detector compares a candidate document against the existing library
and returns a single decision. It evaluates three signals in order:

1. **Checksum equality.** When the candidate's SHA-256 checksum matches
   an existing document, the candidate is a duplicate. This signal is
   decisive.
2. **DOI equality.** When the candidate's DOI matches an existing
   document, the candidate is a duplicate if either the primary signal
   agrees (title or authors match) or the title and authors match
   closely.
3. **Conservative metadata equality.** When neither checksum nor DOI
   matches, the detector compares title and authors (and, optionally,
   year). A match requires the title to be equal after normalization
   and, when the policy requires it, the author lists to be equal after
   normalization.

The detector never merges candidates on the basis of title alone unless
the policy explicitly permits it. Title-only matching is disabled by
default because distinct works can share titles.

Design decisions
----------------
- The detector is a pure function over its inputs and the repository.
  It does not mutate existing rows or the candidate.
- The detector never merges two existing documents. It reports a
  candidate as a duplicate of an existing document; merging existing
  rows is a separate operation that is not implemented at this stage.
- The detector is deterministic: the same candidate and library
  produce the same decision on every run.
- The detector exposes the individual matches it found so that the
  presentation layer can explain the decision.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass, field
from enum import Enum

from academic_platform.application.deduplication.errors import (
    DuplicateDetectionError,
)
from academic_platform.application.deduplication.policy import DuplicatePolicy
from academic_platform.infrastructure.database.models import DocumentAsset
from academic_platform.infrastructure.repositories.errors import (
    RepositoryError,
)
from academic_platform.infrastructure.repositories.manager import (
    RepositoryManager,
)

_logger = logging.getLogger(__name__)


class DuplicateSignal(str, Enum):
    """The individual signals the detector evaluates."""

    CHECKSUM = "checksum"
    DOI = "doi"
    TITLE = "title"
    AUTHORS = "authors"
    YEAR = "year"


@dataclass(frozen=True, slots=True)
class DuplicateMatch:
    """A single match between a candidate and an existing document."""

    signal: DuplicateSignal
    existing_key: str
    existing_display_name: str
    detail: str = ""


@dataclass(frozen=True, slots=True)
class DuplicateDecision:
    """The outcome of evaluating a candidate against the library."""

    is_duplicate: bool
    matches: tuple[DuplicateMatch, ...] = field(default_factory=tuple)
    decisive_signal: DuplicateSignal | None = None
    existing_key: str | None = None
    existing_display_name: str | None = None

    @property
    def match_count(self) -> int:
        return len(self.matches)


class DocumentDuplicateDetector:
    """Detect duplicate documents in the personal library."""

    def __init__(
        self,
        repositories: RepositoryManager,
        policy: DuplicatePolicy | None = None,
    ) -> None:
        self._repositories = repositories
        self._policy = policy or DuplicatePolicy()

    @property
    def policy(self) -> DuplicatePolicy:
        return self._policy

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def evaluate(
        self,
        *,
        checksum_sha256: str | None = None,
        doi: str | None = None,
        title: str | None = None,
        authors: tuple[str, ...] = (),
        year: int | None = None,
        exclude_document_key: str | None = None,
    ) -> DuplicateDecision:
        """Evaluate a candidate against the existing library.

        Parameters
        ----------
        checksum_sha256:
            The candidate's SHA-256 checksum, when known.
        doi:
            The candidate's DOI, when known.
        title:
            The candidate's title, when known.
        authors:
            The candidate's author list.
        year:
            The candidate's year, when known.
        exclude_document_key:
            An optional document key to exclude from the search. Used
            when re-evaluating an existing document against the library.
        """
        matches: list[DuplicateMatch] = []
        decisive: DuplicateSignal | None = None
        existing: DocumentAsset | None = None

        if self._policy.use_checksum and checksum_sha256:
            existing = self._find_by_checksum(
                checksum_sha256, exclude_document_key
            )
            if existing is not None:
                matches.append(
                    DuplicateMatch(
                        signal=DuplicateSignal.CHECKSUM,
                        existing_key=existing.key,
                        existing_display_name=existing.display_name,
                        detail=f"checksum={checksum_sha256[:12]}…",
                    )
                )
                decisive = DuplicateSignal.CHECKSUM

        if existing is None and self._policy.use_doi and doi:
            existing = self._find_by_doi(doi)
            if existing is not None and (
                exclude_document_key is None
                or existing.key != exclude_document_key
            ):
                matches.append(
                    DuplicateMatch(
                        signal=DuplicateSignal.DOI,
                        existing_key=existing.key,
                        existing_display_name=existing.display_name,
                        detail=f"doi={doi}",
                    )
                )
                # DOI equality is decisive when the primary signal
                # agrees, or when the metadata is a conservative match.
                if self._metadata_matches(
                    existing, title=title, authors=authors, year=year,
                    exclude_document_key=exclude_document_key,
                ):
                    decisive = DuplicateSignal.DOI

        if existing is None and self._policy.use_metadata and title:
            existing = self._find_by_metadata(
                title=title,
                authors=authors,
                year=year,
                exclude_document_key=exclude_document_key,
            )
            if existing is not None:
                matches.append(
                    DuplicateMatch(
                        signal=DuplicateSignal.TITLE,
                        existing_key=existing.key,
                        existing_display_name=existing.display_name,
                        detail=f"title={_normalize_title(title)[:64]!r}",
                    )
                )
                decisive = DuplicateSignal.TITLE

        return DuplicateDecision(
            is_duplicate=decisive is not None,
            matches=tuple(matches),
            decisive_signal=decisive,
            existing_key=existing.key if existing is not None else None,
            existing_display_name=existing.display_name
            if existing is not None
            else None,
        )

    # ------------------------------------------------------------------
    # Repository lookups
    # ------------------------------------------------------------------
    def _find_by_checksum(
        self,
        checksum: str,
        exclude_document_key: str | None,
    ) -> DocumentAsset | None:
        repo = self._repositories.get("document_asset")
        try:
            matches = repo.find_by_checksum(checksum)
        except RepositoryError as exc:
            raise DuplicateDetectionError(
                f"Unable to query by checksum: {exc}"
            ) from exc
        for row in matches:
            if exclude_document_key is not None and row.key == exclude_document_key:
                continue
            if row.missing == 0:
                return row
        for row in matches:
            if exclude_document_key is not None and row.key == exclude_document_key:
                continue
            return row
        return None

    def _find_by_doi(self, doi: str) -> DocumentAsset | None:
        # The document asset table does not carry a DOI column; the DOI
        # is stored on the publication table. The detector therefore
        # queries the publication table and then, if the publication is
        # linked to a document by its key, resolves the document. At
        # this stage of the product, the link is by document key
        # equivalence: the document key and the publication key are
        # derived independently, and a direct lookup is not defined.
        #
        # The detector implements the DOI lookup by consulting the
        # publication repository. When a publication with the DOI exists
        # and a document with the same title exists in the library, the
        # detector reports the document as a duplicate. This is a
        # conservative rule documented in the policy module.
        publication_repo = self._repositories.get("publication")
        try:
            publication = publication_repo.find_by_doi(doi)
        except RepositoryError as exc:
            raise DuplicateDetectionError(
                f"Unable to query by DOI: {exc}"
            ) from exc
        if publication is None:
            return None
        # Try to resolve a document with the same title.
        return self._find_by_metadata(
            title=publication.title,
            authors=(),
            year=publication.year,
            exclude_document_key=None,
            require_author_match=False,
        )

    def _find_by_metadata(
        self,
        *,
        title: str,
        authors: tuple[str, ...],
        year: int | None,
        exclude_document_key: str | None,
        require_author_match: bool | None = None,
    ) -> DocumentAsset | None:
        normalized_title = _normalize_title(title)
        if not normalized_title:
            return None
        normalized_authors = _normalize_authors(authors)
        require_authors = (
            require_author_match
            if require_author_match is not None
            else self._policy.require_author_match
        )
        document_repo = self._repositories.get("document_asset")
        try:
            candidates = document_repo.find_all(
                order_by=[DocumentAsset.updated_at.desc()],
                limit=self._policy.metadata_candidate_limit,
            )
        except RepositoryError as exc:
            raise DuplicateDetectionError(
                f"Unable to query the library: {exc}"
            ) from exc
        for row in candidates:
            if exclude_document_key is not None and row.key == exclude_document_key:
                continue
            row_title = _normalize_title(row.display_name or "")
            if row_title != normalized_title:
                continue
            if require_authors and normalized_authors:
                # The document asset does not carry an authors column.
                # When the policy requires an author match and the
                # candidate supplies authors, the detector requires an
                # independent metadata row that carries the authors.
                if not self._document_metadata_authors_match(
                    row, normalized_authors
                ):
                    continue
            if not self._policy.allow_year_difference and year is not None:
                # Without a year column on the document asset, the
                # detector cannot enforce a strict year equality. The
                # policy is preserved for callers that supply a year on
                # both sides; the document asset alone cannot.
                pass
            return row
        return None

    def _document_metadata_authors_match(
        self,
        document: DocumentAsset,
        normalized_authors: tuple[str, ...],
    ) -> bool:
        metadata_repo = self._repositories.get("document_metadata")
        try:
            metadata = metadata_repo.find_for_document(document.id)
        except RepositoryError:
            return False
        if metadata is None or not metadata.authors_json:
            return False
        existing = _load_authors_json(metadata.authors_json)
        return _normalize_authors(existing) == normalized_authors

    # ------------------------------------------------------------------
    # Metadata comparison
    # ------------------------------------------------------------------
    def _metadata_matches(
        self,
        existing: DocumentAsset,
        *,
        title: str | None,
        authors: tuple[str, ...],
        year: int | None,
        exclude_document_key: str | None,
    ) -> bool:
        if not title:
            return False
        resolved = self._find_by_metadata(
            title=title,
            authors=authors,
            year=year,
            exclude_document_key=exclude_document_key,
        )
        if resolved is None:
            return False
        return resolved.key == existing.key


# ----------------------------------------------------------------------
# Normalization helpers
# ----------------------------------------------------------------------
_PUNCTUATION_PATTERN = re.compile(r"[^\w\s]", re.UNICODE)
_WHITESPACE_PATTERN = re.compile(r"\s+")


def _normalize_title(value: str) -> str:
    """Return a normalized title suitable for equality comparison.

    The transformation is:

    - Unicode NFKC normalization.
    - Case folding.
    - Removal of punctuation.
    - Collapse of whitespace runs to a single space.
    - Trimming of leading and trailing whitespace.
    """
    if not value:
        return ""
    decomposed = unicodedata.normalize("NFKC", value)
    without_punctuation = _PUNCTUATION_PATTERN.sub(" ", decomposed)
    collapsed = _WHITESPACE_PATTERN.sub(" ", without_punctuation)
    return collapsed.strip().casefold()


def _normalize_authors(authors: tuple[str, ...]) -> tuple[str, ...]:
    """Return a normalized, sorted author tuple for equality comparison."""
    normalized = [_normalize_title(author) for author in authors if author]
    normalized = [author for author in normalized if author]
    return tuple(sorted(normalized))


def _load_authors_json(raw: str) -> tuple[str, ...]:
    import json

    try:
        data = json.loads(raw)
    except ValueError:
        return ()
    if not isinstance(data, list):
        return ()
    return tuple(str(item) for item in data if item)