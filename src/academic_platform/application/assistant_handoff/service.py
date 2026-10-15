"""Application service for the reader → assistant handoff.

The service composes a handoff payload from a document, its extracted
metadata, its current page, and (optionally) its annotations. It stores
the payload in the handoff store and returns it to the caller.

Design decisions
----------------
- The service reads the document's metadata from the metadata
  repository. It never re-extracts metadata; the extraction pipeline is
  the authoritative source.
- The page excerpt is bounded to a fixed number of characters. The
  bound is a service configuration value; the default is intended for
  display and for short excerpts, not for whole-page text.
- The service never modifies the document or its metadata. The handoff
  is a read-only snapshot.
- The service never commits; it does not write to the database. It
  writes only to the in-process handoff store.
"""

from __future__ import annotations

import logging

from academic_platform.application.assistant_handoff.errors import (
    AssistantHandoffError,
    AssistantHandoffNotFoundError,
)
from academic_platform.application.assistant_handoff.model import (
    AssistantHandoff,
    HandoffOptions,
)
from academic_platform.application.assistant_handoff.store import (
    HandoffStore,
    default_handoff_store,
)
from academic_platform.infrastructure.repositories.errors import (
    RepositoryError,
)
from academic_platform.infrastructure.repositories.manager import (
    RepositoryManager,
)

_logger = logging.getLogger(__name__)

_DEFAULT_EXCERPT_LENGTH = 2000


class AssistantHandoffService:
    """Compose and store handoff payloads."""

    def __init__(
        self,
        repositories: RepositoryManager,
        store: HandoffStore | None = None,
        *,
        excerpt_length: int = _DEFAULT_EXCERPT_LENGTH,
    ) -> None:
        if excerpt_length < 1:
            raise ValueError("excerpt_length must be at least 1")
        self._repositories = repositories
        self._store = store if store is not None else default_handoff_store()
        self._excerpt_length = excerpt_length

    @property
    def store(self) -> HandoffStore:
        return self._store

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def build_handoff(
        self,
        document_key: str,
        *,
        current_page: int | None = None,
        options: HandoffOptions | None = None,
    ) -> AssistantHandoff:
        """Compose a handoff payload and store it."""
        options = options or HandoffOptions()
        document = self._require_document(document_key)
        metadata = self._load_metadata(document.id)

        title = ""
        authors: tuple[str, ...] = ()
        year: int | None = None
        venue: str | None = None
        doi: str | None = None
        abstract: str | None = None
        if options.include_metadata and metadata is not None:
            title = metadata.title or ""
            authors = _load_authors(metadata.authors_json)
            year = metadata.year
            venue = metadata.venue
            doi = metadata.doi
            abstract = metadata.abstract
        if not title:
            title = document.display_name or document.original_filename

        page_excerpt = ""
        if options.include_current_page_text and current_page is not None:
            page_excerpt = self._load_page_excerpt(document.id, current_page)

        annotations: tuple[str, ...] = ()
        if options.include_annotations:
            annotations = self._load_annotation_summaries(document.id)

        handoff = AssistantHandoff(
            document_key=document_key,
            title=title,
            authors=authors,
            year=year,
            venue=venue,
            doi=doi,
            abstract=abstract,
            current_page=current_page,
            page_count=document.page_count,
            page_text_excerpt=page_excerpt,
            annotations=annotations,
            options=options,
        )
        self._store.put(handoff)
        return handoff

    def latest_handoff(self) -> AssistantHandoff | None:
        """Return the most recently stored handoff, or ``None``."""
        return self._store.latest()

    def handoff_for(self, document_key: str) -> AssistantHandoff | None:
        """Return the stored handoff for a document, or ``None``."""
        return self._store.get(document_key)

    def clear_handoffs(self) -> None:
        """Clear every stored handoff."""
        self._store.clear()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _require_document(self, document_key: str):
        repo = self._repositories.get("document_asset")
        try:
            row = repo.find_by_key(document_key)
        except RepositoryError as exc:
            raise AssistantHandoffError(
                f"Unable to read document {document_key!r}: {exc}"
            ) from exc
        if row is None:
            raise AssistantHandoffNotFoundError(
                f"No document with key {document_key!r}"
            )
        return row

    def _load_metadata(self, document_id: int):
        repo = self._repositories.get("document_metadata")
        try:
            return repo.find_for_document(document_id)
        except RepositoryError:
            return None

    def _load_page_excerpt(self, document_id: int, page_number: int) -> str:
        if page_number < 1:
            return ""
        repo = self._repositories.get("document_chunk")
        try:
            chunks = repo.chunks_for_page(document_id, page_number)
        except RepositoryError as exc:
            _logger.warning(
                "Unable to read chunks for page %d: %s", page_number, exc
            )
            return ""
        if not chunks:
            return ""
        text = "\n".join(chunk.content for chunk in chunks if chunk.content)
        text = text.strip()
        if len(text) > self._excerpt_length:
            text = text[: self._excerpt_length].rstrip() + "…"
        return text

    def _load_annotation_summaries(self, document_id: int) -> tuple[str, ...]:
        repo = self._repositories.get("annotation")
        try:
            annotations = repo.list_for_document(document_id)
        except RepositoryError:
            return ()
        summaries: list[str] = []
        for annotation in annotations:
            kind = annotation.kind
            body = (annotation.body or "").strip()
            excerpt = (annotation.text_excerpt or "").strip()
            if kind == "bookmark":
                summaries.append(
                    f"Bookmark on page {annotation.page_number or '?'}"
                )
            elif kind == "highlight":
                summaries.append(
                    f"Highlight on page {annotation.page_number or '?'}: "
                    f"{excerpt[:120] or '(no excerpt)'}"
                )
            else:
                summaries.append(
                    f"Note on page {annotation.page_number or '?'}: "
                    f"{body[:120] or '(no body)'}"
                )
        return tuple(summaries)


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
def _load_authors(authors_json: str | None) -> tuple[str, ...]:
    if not authors_json:
        return ()
    import json

    try:
        data = json.loads(authors_json)
    except ValueError:
        return ()
    if isinstance(data, list):
        return tuple(str(item) for item in data if item)
    if isinstance(data, str):
        return (data,)
    return ()