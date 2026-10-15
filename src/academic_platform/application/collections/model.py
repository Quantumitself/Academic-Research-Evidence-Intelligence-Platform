"""Value objects for the collection service."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class CollectionKind(str, Enum):
    """The kind of a collection."""

    MANUAL = "manual"
    TOPIC = "topic"
    PROJECT = "project"
    SAVED_SEARCH = "saved_search"
    SMART = "smart"

    @property
    def display_name(self) -> str:
        return {
            CollectionKind.MANUAL: "Manual",
            CollectionKind.TOPIC: "Topic",
            CollectionKind.PROJECT: "Project",
            CollectionKind.SAVED_SEARCH: "Saved search",
            CollectionKind.SMART: "Smart",
        }[self]

    @property
    def allows_manual_items(self) -> bool:
        """Return True when the user may add items manually.

        Project-linked and smart collections are managed by their
        underlying rule. Manual, topic, and saved-search collections
        accept items through the collection item API.
        """
        return self in {
            CollectionKind.MANUAL,
            CollectionKind.TOPIC,
            CollectionKind.SAVED_SEARCH,
        }


@dataclass(frozen=True, slots=True)
class CollectionItemView:
    """A collection item as seen by the presentation layer."""

    identifier: int
    item_type: str
    item_identifier: str
    note: str
    position: int
    created_at: str

    @property
    def display_label(self) -> str:
        return self.item_identifier


@dataclass(frozen=True, slots=True)
class CollectionView:
    """A collection as seen by the presentation layer."""

    identifier: int
    key: str
    title: str
    description: str
    kind: CollectionKind
    project_key: str | None
    item_count: int = 0
    created_at: str = ""
    updated_at: str = ""
    version: int = 1
    items: tuple[CollectionItemView, ...] = field(default_factory=tuple)

    @property
    def display_label(self) -> str:
        return self.title or self.key

    @property
    def is_project_linked(self) -> bool:
        return self.kind is CollectionKind.PROJECT and self.project_key is not None