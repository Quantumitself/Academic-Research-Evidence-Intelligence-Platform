"""Repository for collections and collection items."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from academic_platform.infrastructure.database.models import (
    Collection,
    CollectionItem,
)
from academic_platform.infrastructure.repositories.base import Repository
from academic_platform.infrastructure.repositories.errors import (
    DuplicateEntityError,
    RepositoryError,
)


class CollectionRepository(Repository[Collection]):
    """Repository for the ``collection`` table."""

    entity = Collection

    def find_by_key(self, key: str) -> Collection | None:
        """Return the collection with the given stable key, or ``None``."""
        statement = select(Collection).where(Collection.key == key).limit(1)
        try:
            return self._session.execute(statement).scalars().first()
        except SQLAlchemyError as exc:
            raise RepositoryError(f"find_by_key failed: {exc}") from exc

    def list_for_project(self, project_id: int) -> list[Collection]:
        """Return the collections linked to a project, ordered by title."""
        statement = (
            select(Collection)
            .where(Collection.project_id == project_id)
            .order_by(Collection.title)
        )
        try:
            return list(self._session.execute(statement).scalars().all())
        except SQLAlchemyError as exc:
            raise RepositoryError(f"list_for_project failed: {exc}") from exc

    def item_count(self, collection_id: int) -> int:
        """Return the number of items in a collection."""
        statement = select(CollectionItem).where(
            CollectionItem.collection_id == collection_id
        )
        try:
            return len(list(self._session.execute(statement).scalars().all()))
        except SQLAlchemyError as exc:
            raise RepositoryError(f"item_count failed: {exc}") from exc


class CollectionItemRepository(Repository[CollectionItem]):
    """Repository for the ``collection_item`` table."""

    entity = CollectionItem

    def list_for_collection(self, collection_id: int) -> list[CollectionItem]:
        """Return the items of a collection ordered by position."""
        statement = (
            select(CollectionItem)
            .where(CollectionItem.collection_id == collection_id)
            .order_by(CollectionItem.position, CollectionItem.id)
        )
        try:
            return list(self._session.execute(statement).scalars().all())
        except SQLAlchemyError as exc:
            raise RepositoryError(f"list_for_collection failed: {exc}") from exc

    def find_for_target(
        self,
        collection_id: int,
        item_type: str,
        item_identifier: str,
    ) -> CollectionItem | None:
        """Return the item matching the given target, or ``None``."""
        statement = (
            select(CollectionItem)
            .where(
                CollectionItem.collection_id == collection_id,
                CollectionItem.item_type == item_type,
                CollectionItem.item_identifier == item_identifier,
            )
            .limit(1)
        )
        try:
            return self._session.execute(statement).scalars().first()
        except SQLAlchemyError as exc:
            raise RepositoryError(f"find_for_target failed: {exc}") from exc

    def add_item(
        self,
        collection_id: int,
        item_type: str,
        item_identifier: str,
        *,
        note: str = "",
    ) -> CollectionItem:
        """Add an item to a collection, assigning the next position.

        Raises ``DuplicateEntityError`` when the same target is already
        present in the collection.
        """
        existing = self.find_for_target(collection_id, item_type, item_identifier)
        if existing is not None:
            raise DuplicateEntityError(
                f"Item {item_type}/{item_identifier} already present in "
                f"collection {collection_id}"
            )
        position = self._next_position(collection_id)
        item = CollectionItem(
            collection_id=collection_id,
            item_type=item_type,
            item_identifier=item_identifier,
            note=note,
            position=position,
        )
        return self.add(item)

    def remove_item(
        self,
        collection_id: int,
        item_type: str,
        item_identifier: str,
    ) -> bool:
        """Remove an item from a collection.

        Returns True when an item was removed and False when no matching
        item existed.
        """
        existing = self.find_for_target(collection_id, item_type, item_identifier)
        if existing is None:
            return False
        self.delete(existing)
        return True

    def reorder(self, collection_id: int, ordered_identifiers: list[str]) -> int:
        """Assign new positions to the items of a collection.

        The ``ordered_identifiers`` list contains the item identifiers in
        the desired order. Items not present in the list keep their
        current position. Returns the number of rows updated.
        """
        updated = 0
        for position, identifier in enumerate(ordered_identifiers):
            statement = (
                CollectionItem.__table__.update()
                .where(
                    CollectionItem.collection_id == collection_id,
                    CollectionItem.item_identifier == identifier,
                )
                .values(position=position)
            )
            try:
                result = self._session.execute(statement)
            except SQLAlchemyError as exc:
                raise RepositoryError(f"reorder failed: {exc}") from exc
            updated += int(result.rowcount or 0)
        return updated

    def _next_position(self, collection_id: int) -> int:
        statement = (
            select(CollectionItem.position)
            .where(CollectionItem.collection_id == collection_id)
            .order_by(CollectionItem.position.desc())
            .limit(1)
        )
        try:
            current = self._session.execute(statement).scalar()
        except SQLAlchemyError as exc:
            raise RepositoryError(f"_next_position failed: {exc}") from exc
        return int(current or 0) + 1