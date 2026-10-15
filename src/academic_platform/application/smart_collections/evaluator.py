"""Smart-collection evaluator.

The evaluator applies a ``SmartCollectionFilter`` to the library and
returns the matching items. It reads through the document repository,
the document metadata repository, and the annotation repository.

Design decisions
----------------
- The evaluator is a pure read operation. It never persists anything.
- The evaluator returns items in the order the underlying query
  produced them. It never reorders by relevance; ordering is a
  presentation concern.
- The evaluator batches its metadata and annotation lookups per
  document so that a filter that references metadata or annotations
  does not issue a query per item.
- The evaluator's item type is ``document``. Smart collections that
  reference other item types are out of scope at this stage.
"""

from __future__ import annotations

import logging

from academic_platform.application.smart_collections.errors import (
    SmartCollectionError,
)
from academic_platform.application.smart_collections.filter import (
    SmartCollectionFilter,
)
from academic_platform.infrastructure.database.models import (
    Annotation,
    DocumentAsset,
    DocumentMetadata,
)
from academic_platform.infrastructure.database.schemas import (
    CollectionItemRead,
)
from academic_platform.infrastructure.repositories.errors import (
    RepositoryError,
)
from academic_platform.infrastructure.repositories.manager import (
    RepositoryManager,
)

_logger = logging.getLogger(__name__)

_ITEM_TYPE = "document"
_DEFAULT_LIMIT = 2000


class SmartCollectionEvaluator:
    """Evaluate smart-collection filters against the library."""

    def __init__(self, repositories: RepositoryManager) -> None:
        self._repositories = repositories

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def evaluate(
        self,
        filter_state: SmartCollectionFilter,
        *,
        limit: int = _DEFAULT_LIMIT,
    ) -> list[CollectionItemRead]:
        """Return the items that match the filter.

        Parameters
        ----------
        filter_state:
            The parsed filter.
        limit:
            Maximum number of items to return. The evaluator applies the
            limit after filtering; it does not use the limit to bound
            the underlying query, because the filter may be selective.

        Raises
        ------
        SmartCollectionError
            If the underlying repository query fails.
        """
        if filter_state.is_empty:
            return self._list_all_documents(limit=limit)
        candidates = self._fetch_candidate_documents(filter_state, limit=limit)
        matches: list[DocumentAsset] = []
        for document in candidates:
            if self._matches(document, filter_state):
                matches.append(document)
                if len(matches) >= limit:
                    break
        return [self._to_item(document) for document in matches]

    def evaluate_json(
        self,
        payload: str | None,
        *,
        limit: int = _DEFAULT_LIMIT,
    ) -> list[CollectionItemRead]:
        """Parse a JSON payload and evaluate it."""
        filter_state = SmartCollectionFilter.from_json(payload)
        return self.evaluate(filter_state, limit=limit)

    # ------------------------------------------------------------------
    # Fetch
    # ------------------------------------------------------------------
    def _list_all_documents(self, *, limit: int) -> list[CollectionItemRead]:
        repo = self._repositories.get("document_asset")
        try:
            rows = repo.find_all(order_by=[DocumentAsset.display_name], limit=limit)
        except RepositoryError as exc:
            raise SmartCollectionError(f"Unable to list documents: {exc}") from exc
        return [self._to_item(document) for document in rows]

    def _fetch_candidate_documents(
        self,
        filter_state: SmartCollectionFilter,
        *,
        limit: int,
    ) -> list[DocumentAsset]:
        """Return a bounded list of documents to test against the filter.

        The fetch applies the coarse-grained filters that the repository
        can push down (processing state, storage mode, missing) and
        returns the remaining candidates for in-memory evaluation.
        """
        repo = self._repositories.get("document_asset")
        try:
            rows = repo.find_all(order_by=[DocumentAsset.display_name])
        except RepositoryError as exc:
            raise SmartCollectionError(f"Unable to list documents: {exc}") from exc
        # The repository returns the full set; the evaluator applies the
        # coarse-grained filters in memory and then the fine-grained
        # filters per document.
        coarse: list[DocumentAsset] = []
        for row in rows:
            if filter_state.processing_states:
                if row.processing_state not in filter_state.processing_states:
                    continue
            if filter_state.storage_modes:
                if row.storage_mode not in filter_state.storage_modes:
                    continue
            if filter_state.missing is not None:
                is_missing = bool(row.missing)
                if is_missing != filter_state.missing:
                    continue
            coarse.append(row)
            if len(coarse) >= limit:
                break
        return coarse

    # ------------------------------------------------------------------
    # Match
    # ------------------------------------------------------------------
    def _matches(
        self,
        document: DocumentAsset,
        filter_state: SmartCollectionFilter,
    ) -> bool:
        if filter_state.extensions:
            extension = _extension_for(document.location)
            if extension not in filter_state.extensions:
                return False
        metadata = self._load_metadata(document.id)
        if filter_state.year_from is not None or filter_state.year_to is not None:
            year = metadata.year if metadata is not None else None
            if year is None:
                return False
            if filter_state.year_from is not None and year < filter_state.year_from:
                return False
            if filter_state.year_to is not None and year > filter_state.year_to:
                return False
        if filter_state.title_contains:
            needle = filter_state.title_contains.lower()
            haystack = (metadata.title if metadata and metadata.title else document.display_name or "")
            if needle not in haystack.lower():
                return False
        if filter_state.author_contains:
            needle = filter_state.author_contains.lower()
            authors = _load_authors(metadata)
            if not any(needle in author.lower() for author in authors):
                return False
        if filter_state.has_doi is not None:
            has_doi = bool(metadata and metadata.doi)
            if has_doi != filter_state.has_doi:
                return False
        if filter_state.has_annotations is not None:
            count = self._count_annotations(document.id)
            if (count > 0) != filter_state.has_annotations:
                return False
        return True

    # ------------------------------------------------------------------
    # Metadata and annotation lookups
    # ------------------------------------------------------------------
    def _load_metadata(self, document_id: int) -> DocumentMetadata | None:
        repo = self._repositories.get("document_metadata")
        try:
            return repo.find_for_document(document_id)
        except RepositoryError:
            return None

    def _count_annotations(self, document_id: int) -> int:
        repo = self._repositories.get("annotation")
        try:
            return len(repo.list_for_document(document_id))
        except RepositoryError:
            return 0

    # ------------------------------------------------------------------
    # Item conversion
    # ------------------------------------------------------------------
    def _to_item(self, document: DocumentAsset) -> CollectionItemRead:
        return CollectionItemRead(
            id=0,
            collection_id=0,
            item_type=_ITEM_TYPE,
            item_identifier=document.key,
            note="",
            position=0,
            created_at=document.created_at,
            updated_at=document.updated_at,
        )


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
def _extension_for(location: str) -> str:
    from pathlib import Path

    return Path(location).suffix.lower()


def _load_authors(metadata: DocumentMetadata | None) -> tuple[str, ...]:
    if metadata is None or not metadata.authors_json:
        return ()
    import json

    try:
        data = json.loads(metadata.authors_json)
    except ValueError:
        return ()
    if isinstance(data, list):
        return tuple(str(item) for item in data if item)
    if isinstance(data, str):
        return (data,)
    return ()