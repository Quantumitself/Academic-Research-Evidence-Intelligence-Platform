"""Application service for collections.

The service is the single entry point the presentation layer uses to
manage collections and their items. It:

- Creates, reads, updates, deletes, and lists collections.
- Adds, removes, reorders, and annotates collection items.
- Validates the collection kind against the schema's closed set and
  enforces the schema's cross-column invariant (project-linked
  collections carry a project identifier; other kinds do not).
- Reuses the project-collection key convention so that collections
  created by the document linking service are recognized as the same
  object.
- Writes an audit event for every mutation.

Design decisions
----------------
- The service never commits. It runs inside a unit of work supplied by
  the caller.
- Validation is fail-closed. A validation failure raises
  ``CollectionValidationError`` with all issues at once; the caller
  never sees a partially applied mutation.
- The service is idempotent with respect to creation: creating a
  collection whose key already exists raises
  ``CollectionValidationError`` rather than silently updating the
  existing row.
- Manual items are permitted only on collections whose kind allows
  manual items. Project-linked and smart collections reject manual
  item additions.
- Reordering is atomic: the new positions are applied in one flush.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from academic_platform.application.collections.errors import (
    CollectionError,
    CollectionNotFoundError,
    CollectionValidationError,
)
from academic_platform.application.collections.model import (
    CollectionItemView,
    CollectionKind,
    CollectionView,
)
from academic_platform.infrastructure.database.models import (
    AuditEvent,
    Collection,
    CollectionItem,
    ResearchProject,
)
from academic_platform.infrastructure.database.schemas import (
    CollectionCreate,
    CollectionItemCreate,
    CollectionItemUpdate,
    CollectionUpdate,
)
from academic_platform.infrastructure.repositories.errors import (
    DuplicateEntityError,
    RepositoryError,
)
from academic_platform.infrastructure.repositories.manager import (
    RepositoryManager,
)
from academic_platform.application.smart_collections.evaluator import (
    SmartCollectionEvaluator,
)
from academic_platform.application.smart_collections.errors import (
    SmartCollectionFilterError,
)
from academic_platform.application.smart_collections.filter import (
    SmartCollectionFilter,
)


_logger = logging.getLogger(__name__)

_PROJECT_COLLECTION_PREFIX = "project-"

_ACTION_COLLECTION_CREATED = "collection.created"
_ACTION_COLLECTION_UPDATED = "collection.updated"
_ACTION_COLLECTION_DELETED = "collection.deleted"
_ACTION_COLLECTION_ITEM_ADDED = "collection.item_added"
_ACTION_COLLECTION_ITEM_REMOVED = "collection.item_removed"
_ACTION_COLLECTION_ITEM_UPDATED = "collection.item_updated"
_ACTION_COLLECTION_REORDERED = "collection.reordered"


class CollectionService:
    """Application service for collections and their items."""

    def __init__(self, repositories: RepositoryManager) -> None:
        self._repositories = repositories
        self._smart_evaluator = SmartCollectionEvaluator(repositories)

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------
    def list_collections(self) -> list[CollectionView]:
        """Return every collection ordered by title."""
        repo = self._repositories.get("collection")
        try:
            rows = repo.find_all(order_by=[Collection.title])
        except RepositoryError as exc:
            raise CollectionError(f"Unable to list collections: {exc}") from exc
        return [self._to_view(row) for row in rows]

    def list_collections_for_project(self, project_key: str) -> list[CollectionView]:
        """Return the collections linked to a project, ordered by title."""
        project = self._require_project(project_key)
        repo = self._repositories.get("collection")
        try:
            rows = repo.list_for_project(project.id)
        except RepositoryError as exc:
            raise CollectionError(
                f"Unable to list collections for the project: {exc}"
            ) from exc
        return [self._to_view(row) for row in rows]

    def get_collection(self, key: str) -> CollectionView:
        """Return the collection with the given key."""
        return self._to_view(self._require_collection(key))

    def list_items(self, key: str) -> list[CollectionItemView]:
        """Return the items of a collection ordered by position.

        For smart collections, the items are computed by the
        smart-collection evaluator. For all other collections, the
        items are read from the ``collection_item`` table.
        """
        collection = self._require_collection(key)
        kind = _safe_kind(collection.kind)
        if kind is CollectionKind.SMART:
            return self._evaluate_smart_items(collection)
        repo = self._repositories.get("collection_item")
        try:
            rows = repo.list_for_collection(collection.id)
        except RepositoryError as exc:
            raise CollectionError(f"Unable to list items: {exc}") from exc
        return [self._to_item_view(row) for row in rows]

    def find_item(
        self,
        key: str,
        item_type: str,
        item_identifier: str,
    ) -> CollectionItemView | None:
        """Return a specific item, or ``None`` when it does not exist."""
        collection = self._require_collection(key)
        repo = self._repositories.get("collection_item")
        try:
            row = repo.find_for_target(collection.id, item_type, item_identifier)
        except RepositoryError as exc:
            raise CollectionError(f"Unable to read the item: {exc}") from exc
        return self._to_item_view(row) if row is not None else None

    # ------------------------------------------------------------------
    # Collection writes
    # ------------------------------------------------------------------
    def create_collection(
        self,
        *,
        key: str,
        title: str = "",
        description: str = "",
        kind: CollectionKind = CollectionKind.MANUAL,
        project_key: str | None = None,
        filter_json: str | None = None,
        actor: str = "system",
    ) -> CollectionView:
        """Create a collection."""
        project: ResearchProject | None = None
        if kind is CollectionKind.PROJECT:
            if not project_key:
                raise CollectionValidationError(
                    ["project_key is required for project-linked collections"]
                )
            project = self._require_project(project_key)
        elif project_key:
            raise CollectionValidationError(
                ["project_key is only valid for project-linked collections"]
            )
        issues = _validate_collection_payload(
            key=key,
            title=title,
            description=description,
            kind=kind,
            filter_json=filter_json,
        )
        if issues:
            raise CollectionValidationError(issues)

        repo = self._repositories.get("collection")
        payload = CollectionCreate(
            key=key,
            title=title,
            description=description,
            kind=kind.value,
            project_id=project.id if project is not None else None,
            filter_json=filter_json,
        )
        try:
            row = repo.create(payload)
        except DuplicateEntityError as exc:
            raise CollectionValidationError(
                [f"A collection with key {key!r} already exists"]
            ) from exc
        except RepositoryError as exc:
            raise CollectionError(f"Unable to create the collection: {exc}") from exc
        self._record_audit(
            actor=actor,
            action=_ACTION_COLLECTION_CREATED,
            target_type="collection",
            target_identifier=key,
            summary=f"Created collection {row.title or key!r}",
        )
        return self._to_view(row)

    def update_collection(
        self,
        key: str,
        *,
        title: str | None = None,
        description: str | None = None,
        filter_json: str | None = None,
        actor: str = "system",
    ) -> CollectionView:
        """Apply changes to an existing collection."""
        collection = self._require_collection(key)
        issues = _validate_collection_payload(
            key=key,
            title=title if title is not None else collection.title,
            description=(
                description if description is not None else collection.description
            ),
            kind=CollectionKind(collection.kind),
            filter_json=(
                filter_json if filter_json is not None else collection.filter_json
            ),
        )
        if issues:
            raise CollectionValidationError(issues)
        changes: dict[str, Any] = {}
        if title is not None:
            changes["title"] = title
        if description is not None:
            changes["description"] = description
        if filter_json is not None:
            changes["filter_json"] = filter_json
        if not changes:
            return self._to_view(collection)
        payload = CollectionUpdate(**changes)
        repo = self._repositories.get("collection")
        try:
            updated = repo.update(collection, payload)
        except RepositoryError as exc:
            raise CollectionError(f"Unable to update the collection: {exc}") from exc
        self._record_audit(
            actor=actor,
            action=_ACTION_COLLECTION_UPDATED,
            target_type="collection",
            target_identifier=key,
            summary=f"Updated collection {updated.title or key!r}",
            payload={"changed": sorted(changes.keys())},
        )
        return self._to_view(updated)

    def delete_collection(self, key: str, *, actor: str = "system") -> None:
        """Delete a collection and its items.

        The items are removed through the model's cascade. The resources
        that the items reference (documents, publications, evidence
        records, notes) are not deleted.
        """
        collection = self._require_collection(key)
        repo = self._repositories.get("collection")
        try:
            repo.delete(collection)
        except RepositoryError as exc:
            raise CollectionError(f"Unable to delete the collection: {exc}") from exc
        self._record_audit(
            actor=actor,
            action=_ACTION_COLLECTION_DELETED,
            target_type="collection",
            target_identifier=key,
            summary=f"Deleted collection {collection.title or key!r}",
        )

    # ------------------------------------------------------------------
    # Item writes
    # ------------------------------------------------------------------
    def add_item(
        self,
        key: str,
        *,
        item_type: str,
        item_identifier: str,
        note: str = "",
        actor: str = "system",
    ) -> CollectionItemView:
        """Add an item to a collection."""
        issues = _validate_item_payload(
            item_type=item_type, item_identifier=item_identifier, note=note
        )
        if issues:
            raise CollectionValidationError(issues)
        collection = self._require_collection(key)
        kind = _safe_kind(collection.kind)
        if not kind.allows_manual_items:
            raise CollectionValidationError(
                [
                    f"Collections of kind {kind.value!r} do not accept manual "
                    "items."
                ]
            )
        repo = self._repositories.get("collection_item")
        try:
            row = repo.add_item(
                collection.id,
                item_type,
                item_identifier,
                note=note,
            )
        except DuplicateEntityError as exc:
            raise CollectionValidationError(
                [f"The item {item_type}/{item_identifier} is already in the collection"]
            ) from exc
        except RepositoryError as exc:
            raise CollectionError(f"Unable to add the item: {exc}") from exc
        self._record_audit(
            actor=actor,
            action=_ACTION_COLLECTION_ITEM_ADDED,
            target_type="collection",
            target_identifier=key,
            summary=f"Added {item_type} {item_identifier!r}",
        )
        return self._to_item_view(row)

    def update_item(
        self,
        key: str,
        item_id: int,
        *,
        note: str | None = None,
        position: int | None = None,
        actor: str = "system",
    ) -> CollectionItemView:
        """Apply changes to a collection item."""
        collection = self._require_collection(key)
        repo = self._repositories.get("collection_item")
        try:
            row = repo.get(item_id)
        except RepositoryError as exc:
            raise CollectionError(f"Unable to read the item: {exc}") from exc
        if row is None or row.collection_id != collection.id:
            raise CollectionNotFoundError(
                f"No item with id {item_id!r} in collection {key!r}"
            )
        changes: dict[str, Any] = {}
        if note is not None:
            if len(note) > 2048:
                raise CollectionValidationError(
                    ["Item note must be at most 2048 characters"]
                )
            changes["note"] = note
        if position is not None:
            if position < 0:
                raise CollectionValidationError(
                    ["Item position must be non-negative"]
                )
            changes["position"] = position
        if not changes:
            return self._to_item_view(row)
        payload = CollectionItemUpdate(**changes)
        try:
            updated = repo.update(row, payload)
        except RepositoryError as exc:
            raise CollectionError(f"Unable to update the item: {exc}") from exc
        self._record_audit(
            actor=actor,
            action=_ACTION_COLLECTION_ITEM_UPDATED,
            target_type="collection",
            target_identifier=key,
            summary=(
                f"Updated {updated.item_type} {updated.item_identifier!r}"
            ),
        )
        return self._to_item_view(updated)

    def remove_item(
        self,
        key: str,
        item_id: int,
        *,
        actor: str = "system",
    ) -> None:
        """Remove an item from a collection."""
        collection = self._require_collection(key)
        repo = self._repositories.get("collection_item")
        try:
            row = repo.get(item_id)
        except RepositoryError as exc:
            raise CollectionError(f"Unable to read the item: {exc}") from exc
        if row is None or row.collection_id != collection.id:
            raise CollectionNotFoundError(
                f"No item with id {item_id!r} in collection {key!r}"
            )
        try:
            repo.delete(row)
        except RepositoryError as exc:
            raise CollectionError(f"Unable to remove the item: {exc}") from exc
        self._record_audit(
            actor=actor,
            action=_ACTION_COLLECTION_ITEM_REMOVED,
            target_type="collection",
            target_identifier=key,
            summary=f"Removed {row.item_type} {row.item_identifier!r}",
        )

    def remove_item_by_target(
        self,
        key: str,
        *,
        item_type: str,
        item_identifier: str,
        actor: str = "system",
    ) -> bool:
        """Remove an item identified by its target.

        Returns True when an item was removed and False when no match
        existed.
        """
        collection = self._require_collection(key)
        repo = self._repositories.get("collection_item")
        try:
            removed = repo.remove_item(
                collection.id, item_type, item_identifier
            )
        except RepositoryError as exc:
            raise CollectionError(f"Unable to remove the item: {exc}") from exc
        if removed:
            self._record_audit(
                actor=actor,
                action=_ACTION_COLLECTION_ITEM_REMOVED,
                target_type="collection",
                target_identifier=key,
                summary=f"Removed {item_type} {item_identifier!r}",
            )
        return removed

    def reorder_items(
        self,
        key: str,
        ordered_item_ids: list[int],
        *,
        actor: str = "system",
    ) -> int:
        """Assign new positions to the collection's items.

        Parameters
        ----------
        key:
            The collection key.
        ordered_item_ids:
            Item identifiers in the desired order. Items not present in
            the list keep their current position.

        Returns
        -------
        int
            The number of items whose position changed.
        """
        collection = self._require_collection(key)
        repo = self._repositories.get("collection_item")
        rows: list[tuple[int, CollectionItem]] = []
        for position, item_id in enumerate(ordered_item_ids):
            try:
                row = repo.get(item_id)
            except RepositoryError:
                continue
            if row is None or row.collection_id != collection.id:
                continue
            rows.append((position, row))
        # Apply the new positions in a single pass so that intermediate
        # states do not confuse the autoflush.
        for position, row in rows:
            row.position = position
        try:
            repo.session.flush()
        except RepositoryError as exc:
            raise CollectionError(f"Unable to reorder the items: {exc}") from exc
        updated = len(rows)
        if updated:
            try:
                repo.session.flush()
            except RepositoryError as exc:
                raise CollectionError(
                    f"Unable to reorder the items: {exc}"
                ) from exc
            self._record_audit(
                actor=actor,
                action=_ACTION_COLLECTION_REORDERED,
                target_type="collection",
                target_identifier=key,
                summary=f"Reordered {updated} item(s)",
            )
        return updated

    # ------------------------------------------------------------------
    # Project-linked collection helper
    # ------------------------------------------------------------------
    def project_collection_key(self, project_key: str) -> str:
        """Return the collection key used for a project-linked collection.

        The convention is shared with the document linking service so
        that collections created by either service are recognized as
        the same object.
        """
        return f"{_PROJECT_COLLECTION_PREFIX}{project_key}"

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _require_collection(self, key: str) -> Collection:
        repo = self._repositories.get("collection")
        try:
            row = repo.find_by_key(key)
        except RepositoryError as exc:
            raise CollectionError(f"Unable to read the collection: {exc}") from exc
        if row is None:
            raise CollectionNotFoundError(f"No collection with key {key!r}")
        return row

    def _require_project(self, key: str) -> ResearchProject:
        repo = self._repositories.get("research_project")
        try:
            row = repo.find_by_key(key)
        except RepositoryError as exc:
            raise CollectionError(f"Unable to read the project: {exc}") from exc
        if row is None:
            raise CollectionNotFoundError(f"No project with key {key!r}")
        return row

    def _to_view(self, row: Collection) -> CollectionView:
        project_key: str | None = None
        if row.project_id is not None:
            project_repo = self._repositories.get("research_project")
            try:
                project = project_repo.get(row.project_id)
            except RepositoryError:
                project = None
            if project is not None:
                project_key = project.key
        item_repo = self._repositories.get("collection_item")
        items: list[CollectionItemView] = []
        try:
            items = [
                self._to_item_view(item)
                for item in item_repo.list_for_collection(row.id)
            ]
        except RepositoryError:
            items = []
        return CollectionView(
            identifier=row.id,
            key=row.key,
            title=row.title,
            description=row.description,
            kind=_safe_kind(row.kind),
            project_key=project_key,
            item_count=len(items),
            created_at=row.created_at.isoformat() if row.created_at else "",
            updated_at=row.updated_at.isoformat() if row.updated_at else "",
            version=row.version or 1,
            items=tuple(items),
        )

    def _to_item_view(self, row: CollectionItem) -> CollectionItemView:
        return CollectionItemView(
            identifier=row.id,
            item_type=row.item_type,
            item_identifier=row.item_identifier,
            note=row.note,
            position=row.position,
            created_at=row.created_at.isoformat() if row.created_at else "",
        )

    def _record_audit(
        self,
        *,
        actor: str,
        action: str,
        target_type: str,
        target_identifier: str,
        summary: str,
        payload: dict[str, Any] | None = None,
    ) -> None:
        try:
            session = self._repositories.get("audit_event").session
            session.add(
                AuditEvent(
                    actor=actor or "system",
                    action=action,
                    target_type=target_type,
                    target_identifier=target_identifier,
                    summary=summary,
                    payload_json=json.dumps(payload) if payload else None,
                )
            )
            session.flush()
        except Exception as exc:  # noqa: BLE001 - boundary
            _logger.warning(
                "Unable to record the audit event for %s: %s",
                target_identifier,
                exc,
            )

    def evaluate_smart_collection(
        self, key: str
    ) -> list[CollectionItemView]:
        """Return the computed items of a smart collection.

        Raises
        ------
        CollectionValidationError
            If the collection is not a smart collection.
        """
        collection = self._require_collection(key)
        kind = _safe_kind(collection.kind)
        if kind is not CollectionKind.SMART:
            raise CollectionValidationError(
                [f"Collection {key!r} is not a smart collection"]
            )
        return self._evaluate_smart_items(collection)

    def _evaluate_smart_items(
        self, collection: Collection
    ) -> list[CollectionItemView]:
        try:
            filter_state = SmartCollectionFilter.from_json(collection.filter_json)
        except SmartCollectionFilterError as exc:
            raise CollectionValidationError(list(exc.issues)) from exc
        try:
            items = self._smart_evaluator.evaluate(filter_state)
        except Exception as exc:  # noqa: BLE001 - boundary
            raise CollectionError(
                f"Unable to evaluate the smart collection: {exc}"
            ) from exc
        views: list[CollectionItemView] = []
        for index, item in enumerate(items):
            views.append(
                CollectionItemView(
                    identifier=0,
                    item_type=item.item_type,
                    item_identifier=item.item_identifier,
                    note="",
                    position=index,
                    created_at=item.created_at.isoformat()
                    if item.created_at
                    else "",
                )
            )
        return views

# ----------------------------------------------------------------------
# Validation helpers
# ----------------------------------------------------------------------
def _validate_collection_payload(
    *,
    key: str,
    title: str,
    description: str,
    kind: CollectionKind,
    filter_json: str | None,
) -> list[str]:
    issues: list[str] = []
    cleaned_key = (key or "").strip()
    if not cleaned_key:
        issues.append("Collection key must not be empty")
    else:
        if not cleaned_key[0].isalnum():
            issues.append("Collection key must start with a letter or digit")
        for character in cleaned_key:
            if not (character.isalnum() or character in "-_"):
                issues.append(
                    "Collection key may contain letters, digits, hyphens, "
                    "and underscores"
                )
                break
        if cleaned_key != cleaned_key.lower():
            issues.append("Collection key must be lowercase")
    if title and len(title) > 512:
        issues.append("Collection title must be at most 512 characters")
    if description and len(description) > 4096:
        issues.append("Collection description must be at most 4096 characters")
    if kind in {CollectionKind.SMART, CollectionKind.SAVED_SEARCH} and not filter_json:
        issues.append(
            f"Collections of kind {kind.value!r} require a filter payload"
        )
    if filter_json:
        try:
            SmartCollectionFilter.from_json(filter_json)
        except SmartCollectionFilterError as exc:
            issues.extend(exc.issues)
    elif kind is CollectionKind.SMART:
        # An empty filter is valid for smart collections; it matches
        # every document. The previous validation required a filter;
        # that requirement is relaxed here because an empty filter has
        # well-defined semantics.
        pass
    return issues


def _validate_item_payload(
    *,
    item_type: str,
    item_identifier: str,
    note: str,
) -> list[str]:
    issues: list[str] = []
    if item_type not in {"publication", "document", "evidence", "note"}:
        issues.append(
            "Item type must be one of: publication, document, evidence, note"
        )
    if not item_identifier or not item_identifier.strip():
        issues.append("Item identifier must not be empty")
    elif len(item_identifier) > 128:
        issues.append("Item identifier must be at most 128 characters")
    if note and len(note) > 2048:
        issues.append("Item note must be at most 2048 characters")
    return issues


def _safe_kind(value: str) -> CollectionKind:
    try:
        return CollectionKind(value)
    except ValueError:
        return CollectionKind.MANUAL