"""Application service for annotations.

The service persists annotations through the ``annotation`` repository
and keeps the FTS5 note index synchronized with the annotation content.
It is the single entry point the reader page uses to create, update,
list, and delete annotations.

Design decisions
----------------
- The service validates inputs against the persistence schema before
  writing. It never persists an annotation that fails validation.
- The service keeps the FTS5 index in sync: creating or updating an
  annotation re-indexes it; deleting an annotation removes its FTS5
  row.
- The service never modifies the source PDF. Annotations are separate
  records linked to the document and its page.
- The service never commits. It runs inside a unit of work supplied by
  the caller.
- The service exposes an export method that returns a list of
  annotation views suitable for serialization to JSON, Markdown, or a
  sidecar file. Writing the export to disk is the caller's
  responsibility.
"""

from __future__ import annotations

import logging
from dataclasses import replace

from academic_platform.application.annotations.errors import (
    AnnotationError,
    AnnotationNotFoundError,
)
from academic_platform.application.annotations.model import (
    AnnotationColor,
    AnnotationKind,
    AnnotationView,
)
from academic_platform.infrastructure.database.models import (
    Annotation,
    DocumentAsset,
)
from academic_platform.infrastructure.database.schemas import (
    AnnotationCreate,
    AnnotationUpdate,
)
from academic_platform.infrastructure.full_text_search.errors import (
    FtsError,
)
from academic_platform.infrastructure.full_text_search.indexer import (
    FtsIndexer,
)
from academic_platform.infrastructure.repositories.errors import (
    RepositoryError,
)
from academic_platform.infrastructure.repositories.manager import (
    RepositoryManager,
)

_logger = logging.getLogger(__name__)


class AnnotationService:
    """Application service for document annotations."""

    def __init__(self, repositories: RepositoryManager) -> None:
        self._repositories = repositories

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------
    def list_for_document(self, document_key: str) -> list[AnnotationView]:
        """Return the annotations of a document ordered by page and id."""
        document = self._require_document(document_key)
        repo = self._repositories.get("annotation")
        try:
            rows = repo.list_for_document(document.id)
        except RepositoryError as exc:
            raise AnnotationError(f"Unable to list annotations: {exc}") from exc
        return [self._to_view(row, document_key) for row in rows]

    def list_bookmarks(self, document_key: str) -> list[AnnotationView]:
        """Return the bookmarks of a document ordered by page."""
        document = self._require_document(document_key)
        repo = self._repositories.get("annotation")
        try:
            rows = repo.list_bookmarks(document.id)
        except RepositoryError as exc:
            raise AnnotationError(f"Unable to list bookmarks: {exc}") from exc
        return [self._to_view(row, document_key) for row in rows]

    def list_for_page(self, document_key: str, page_number: int) -> list[AnnotationView]:
        """Return the annotations on a specific page."""
        document = self._require_document(document_key)
        repo = self._repositories.get("annotation")
        try:
            rows = repo.list_for_page(document.id, page_number)
        except RepositoryError as exc:
            raise AnnotationError(f"Unable to list page annotations: {exc}") from exc
        return [self._to_view(row, document_key) for row in rows]

    def get(self, annotation_id: int) -> AnnotationView:
        """Return a single annotation by identifier."""
        repo = self._repositories.get("annotation")
        try:
            row = repo.get(annotation_id)
        except RepositoryError as exc:
            raise AnnotationError(f"Unable to read annotation: {exc}") from exc
        if row is None:
            raise AnnotationNotFoundError(
                f"No annotation with id {annotation_id!r}"
            )
        document = self._get_document_by_id(row.document_id)
        document_key = document.key if document is not None else ""
        return self._to_view(row, document_key)

    # ------------------------------------------------------------------
    # Writes
    # ------------------------------------------------------------------
    def create_note(
        self,
        document_key: str,
        page_number: int,
        body: str,
        *,
        anchor: str | None = None,
        text_excerpt: str | None = None,
    ) -> AnnotationView:
        """Create a note on a document page."""
        return self._create(
            document_key=document_key,
            kind=AnnotationKind.NOTE,
            page_number=page_number,
            body=body,
            anchor=anchor,
            text_excerpt=text_excerpt,
            color=None,
        )

    def create_highlight(
        self,
        document_key: str,
        page_number: int,
        text_excerpt: str,
        *,
        color: AnnotationColor = AnnotationColor.YELLOW,
        anchor: str | None = None,
        body: str = "",
    ) -> AnnotationView:
        """Create a highlight on a document page."""
        return self._create(
            document_key=document_key,
            kind=AnnotationKind.HIGHLIGHT,
            page_number=page_number,
            body=body,
            anchor=anchor,
            text_excerpt=text_excerpt,
            color=color,
        )

    def create_bookmark(
        self,
        document_key: str,
        page_number: int,
        *,
        body: str = "",
    ) -> AnnotationView:
        """Create a bookmark on a document page."""
        return self._create(
            document_key=document_key,
            kind=AnnotationKind.BOOKMARK,
            page_number=page_number,
            body=body,
            anchor=None,
            text_excerpt=None,
            color=None,
        )

    def update(
        self,
        annotation_id: int,
        *,
        body: str | None = None,
        text_excerpt: str | None = None,
        anchor: str | None = None,
        color: AnnotationColor | None = None,
        page_number: int | None = None,
    ) -> AnnotationView:
        """Update the mutable fields of an annotation.

        Only the fields that are explicitly supplied are changed. The
        annotation's kind cannot be changed.
        """
        repo = self._repositories.get("annotation")
        try:
            row = repo.get(annotation_id)
        except RepositoryError as exc:
            raise AnnotationError(f"Unable to read annotation: {exc}") from exc
        if row is None:
            raise AnnotationNotFoundError(
                f"No annotation with id {annotation_id!r}"
            )
        changes: dict[str, object] = {}
        if body is not None:
            changes["body"] = body
        if text_excerpt is not None:
            changes["text_excerpt"] = text_excerpt
        if anchor is not None:
            changes["anchor"] = anchor
        if color is not None:
            changes["color"] = color.value
        if page_number is not None:
            if page_number < 1:
                raise AnnotationError("page_number must be at least 1")
            changes["page_number"] = page_number
        if not changes:
            document = self._get_document_by_id(row.document_id)
            document_key = document.key if document is not None else ""
            return self._to_view(row, document_key)
        payload = AnnotationUpdate(**changes)
        try:
            updated = repo.update(row, payload)
        except RepositoryError as exc:
            raise AnnotationError(f"Unable to update annotation: {exc}") from exc
        document = self._get_document_by_id(updated.document_id)
        document_key = document.key if document is not None else ""
        self._reindex(updated, document_key)
        return self._to_view(updated, document_key)

    def delete(self, annotation_id: int) -> None:
        """Delete an annotation and remove its FTS5 row."""
        repo = self._repositories.get("annotation")
        try:
            row = repo.get(annotation_id)
        except RepositoryError as exc:
            raise AnnotationError(f"Unable to read annotation: {exc}") from exc
        if row is None:
            raise AnnotationNotFoundError(
                f"No annotation with id {annotation_id!r}"
            )
        try:
            session = repo.session
            FtsIndexer(session).remove_annotation(annotation_id)
            repo.delete(row)
        except RepositoryError as exc:
            raise AnnotationError(f"Unable to delete annotation: {exc}") from exc
        except FtsError as exc:
            raise AnnotationError(f"Unable to update the search index: {exc}") from exc

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------
    def export_views(self, document_key: str) -> list[AnnotationView]:
        """Return every annotation of a document for export."""
        return self.list_for_document(document_key)

    def export_to_json(self, document_key: str) -> str:
        """Return a JSON serialization of a document's annotations."""
        import json

        views = self.list_for_document(document_key)
        payload = [
            {
                "id": view.identifier,
                "document_key": view.document_key,
                "kind": view.kind.value,
                "page_number": view.page_number,
                "body": view.body,
                "text_excerpt": view.text_excerpt,
                "anchor": view.anchor,
                "color": view.color.value if view.color is not None else None,
                "created_at": view.created_at,
                "updated_at": view.updated_at,
                "version": view.version,
            }
            for view in views
        ]
        return json.dumps(payload, indent=2, sort_keys=True)

    def export_to_markdown(self, document_key: str) -> str:
        """Return a Markdown serialization of a document's annotations."""
        views = self.list_for_document(document_key)
        lines: list[str] = [f"# Annotations for {document_key}", ""]
        for view in views:
            heading = view.kind.value.capitalize()
            page = view.page_number if view.page_number is not None else "?"
            lines.append(f"## {heading} (page {page})")
            lines.append("")
            if view.text_excerpt:
                lines.append(f"> {view.text_excerpt}")
                lines.append("")
            if view.body:
                lines.append(view.body)
                lines.append("")
            if view.color is not None:
                lines.append(f"_Color: {view.color.value}_")
                lines.append("")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _create(
        self,
        *,
        document_key: str,
        kind: AnnotationKind,
        page_number: int,
        body: str,
        anchor: str | None,
        text_excerpt: str | None,
        color: AnnotationColor | None,
    ) -> AnnotationView:
        if page_number < 1:
            raise AnnotationError("page_number must be at least 1")
        document = self._require_document(document_key)
        repo = self._repositories.get("annotation")
        payload = AnnotationCreate(
            document_id=document.id,
            kind=kind.value,
            page_number=page_number,
            text_excerpt=text_excerpt,
            body=body or "",
            anchor=anchor,
            color=color.value if color is not None else None,
        )
        try:
            row = repo.create(payload)
        except RepositoryError as exc:
            raise AnnotationError(f"Unable to create annotation: {exc}") from exc
        self._reindex(row, document_key)
        return self._to_view(row, document_key)

    def _reindex(self, row: Annotation, document_key: str) -> None:
        if not document_key:
            return
        try:
            session = self._repositories.get("annotation").session
            FtsIndexer(session).index_annotation(row, document_key)
        except FtsError as exc:
            _logger.warning(
                "Unable to update the FTS index for annotation %d: %s",
                row.id,
                exc,
            )
        except Exception as exc:  # noqa: BLE001 - boundary
            _logger.exception(
                "Unexpected error indexing annotation %d", row.id
            )

    def _require_document(self, document_key: str) -> DocumentAsset:
        repo = self._repositories.get("document_asset")
        try:
            document = repo.find_by_key(document_key)
        except RepositoryError as exc:
            raise AnnotationError(f"Unable to read document: {exc}") from exc
        if document is None:
            raise AnnotationError(f"No document with key {document_key!r}")
        return document

    def _get_document_by_id(self, document_id: int) -> DocumentAsset | None:
        repo = self._repositories.get("document_asset")
        try:
            return repo.get(document_id)
        except RepositoryError:
            return None

    def _to_view(self, row: Annotation, document_key: str) -> AnnotationView:
        try:
            kind = AnnotationKind(row.kind)
        except ValueError:
            kind = AnnotationKind.NOTE
        color: AnnotationColor | None = None
        if row.color:
            try:
                color = AnnotationColor(row.color)
            except ValueError:
                color = None
        return AnnotationView(
            identifier=row.id,
            document_key=document_key,
            kind=kind,
            page_number=row.page_number,
            body=row.body or "",
            text_excerpt=row.text_excerpt or "",
            anchor=row.anchor,
            color=color,
            created_at=row.created_at.isoformat() if row.created_at else "",
            updated_at=row.updated_at.isoformat() if row.updated_at else "",
            version=row.version or 1,
        )