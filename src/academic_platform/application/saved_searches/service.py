"""Application service for saved searches.

The service is the single entry point the presentation layer uses to
create, list, update, delete, and mark-executed saved searches. It is
constructed with a repository manager and validates every payload
through the persistence schemas.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from academic_platform.application.saved_searches.errors import (
    SavedSearchError,
    SavedSearchNotFoundError,
)
from academic_platform.application.saved_searches.model import (
    SavedSearch,
)
from academic_platform.infrastructure.database.models import (
    SavedSearchQuery,
)
from academic_platform.infrastructure.database.schemas import (
    SavedSearchQueryCreate,
    SavedSearchQueryUpdate,
)
from academic_platform.infrastructure.repositories.errors import (
    DuplicateEntityError,
    RepositoryError,
)
from academic_platform.infrastructure.repositories.manager import (
    RepositoryManager,
)

_logger = logging.getLogger(__name__)


class SavedSearchService:
    """Application service for saved search definitions."""

    def __init__(self, repositories: RepositoryManager) -> None:
        self._repositories = repositories

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------
    def list_all(self) -> list[SavedSearch]:
        """Return every saved search ordered by name."""
        repo = self._repositories.get("saved_search_query")
        try:
            rows = repo.list_all_ordered()
        except RepositoryError as exc:
            raise SavedSearchError(f"Unable to list saved searches: {exc}") from exc
        return [self._to_model(row) for row in rows]

    def get_by_key(self, key: str) -> SavedSearch:
        """Return the saved search with the given key.

        Raises
        ------
        SavedSearchNotFoundError
            If no saved search matches the key.
        """
        repo = self._repositories.get("saved_search_query")
        try:
            row = repo.find_by_key(key)
        except RepositoryError as exc:
            raise SavedSearchError(f"Unable to read saved search: {exc}") from exc
        if row is None:
            raise SavedSearchNotFoundError(f"No saved search with key {key!r}")
        return self._to_model(row)

    # ------------------------------------------------------------------
    # Writes
    # ------------------------------------------------------------------
    def create(self, search: SavedSearch) -> SavedSearch:
        """Persist a new saved search."""
        repo = self._repositories.get("saved_search_query")
        payload = SavedSearchQueryCreate(
            key=search.key,
            name=search.name,
            query_text=search.query_text,
            scope=search.scope,
            filter_json=json.dumps(search.filters) if search.filters else None,
            source_ids_json=json.dumps(list(search.source_keys)),
        )
        try:
            row = repo.create(payload)
        except DuplicateEntityError as exc:
            raise SavedSearchError(
                f"A saved search with key {search.key!r} already exists"
            ) from exc
        except RepositoryError as exc:
            raise SavedSearchError(f"Unable to create saved search: {exc}") from exc
        return self._to_model(row)

    def update(self, key: str, **changes: Any) -> SavedSearch:
        """Apply changes to an existing saved search.

        The supported fields are ``name``, ``query_text``, ``scope``,
        ``filters``, and ``source_keys``. Unknown fields are ignored.
        """
        repo = self._repositories.get("saved_search_query")
        try:
            row = repo.find_by_key(key)
        except RepositoryError as exc:
            raise SavedSearchError(f"Unable to read saved search: {exc}") from exc
        if row is None:
            raise SavedSearchNotFoundError(f"No saved search with key {key!r}")
        payload_changes: dict[str, Any] = {}
        if "name" in changes:
            payload_changes["name"] = changes["name"]
        if "query_text" in changes:
            payload_changes["query_text"] = changes["query_text"]
        if "scope" in changes:
            payload_changes["scope"] = changes["scope"]
        if "filters" in changes:
            filters = changes["filters"] or {}
            payload_changes["filter_json"] = (
                json.dumps(filters) if filters else None
            )
        if "source_keys" in changes:
            source_keys = changes["source_keys"] or ()
            payload_changes["source_ids_json"] = json.dumps(list(source_keys))
        payload = SavedSearchQueryUpdate(**payload_changes)
        try:
            updated = repo.update(row, payload)
        except RepositoryError as exc:
            raise SavedSearchError(f"Unable to update saved search: {exc}") from exc
        return self._to_model(updated)

    def delete(self, key: str) -> None:
        """Delete a saved search by key."""
        repo = self._repositories.get("saved_search_query")
        try:
            row = repo.find_by_key(key)
        except RepositoryError as exc:
            raise SavedSearchError(f"Unable to read saved search: {exc}") from exc
        if row is None:
            raise SavedSearchNotFoundError(f"No saved search with key {key!r}")
        try:
            repo.delete(row)
        except RepositoryError as exc:
            raise SavedSearchError(f"Unable to delete saved search: {exc}") from exc

    def mark_executed(self, key: str) -> SavedSearch:
        """Record that a saved search was just executed."""
        repo = self._repositories.get("saved_search_query")
        try:
            row = repo.find_by_key(key)
        except RepositoryError as exc:
            raise SavedSearchError(f"Unable to read saved search: {exc}") from exc
        if row is None:
            raise SavedSearchNotFoundError(f"No saved search with key {key!r}")
        try:
            updated = repo.mark_executed(row.id)
        except RepositoryError as exc:
            raise SavedSearchError(f"Unable to mark saved search: {exc}") from exc
        return self._to_model(updated)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _to_model(self, row: SavedSearchQuery) -> SavedSearch:
        return SavedSearch(
            key=row.key,
            name=row.name,
            query_text=row.query_text,
            scope=row.scope,
            filters=_load_json_dict(row.filter_json),
            source_keys=tuple(_load_json_list(row.source_ids_json)),
            last_executed_at=row.last_executed_at,
        )


def _load_json_dict(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except ValueError:
        return {}
    if not isinstance(data, dict):
        return {}
    return data


def _load_json_list(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except ValueError:
        return []
    if not isinstance(data, list):
        return []
    return [str(item) for item in data]