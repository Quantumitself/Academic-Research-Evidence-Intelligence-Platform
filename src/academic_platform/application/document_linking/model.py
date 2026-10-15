"""Value objects for the document linking service."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class LinkTarget(str, Enum):
    """The kind of target a document can be linked to."""

    COLLECTION = "collection"
    PROJECT = "project"


@dataclass(frozen=True, slots=True)
class CollectionOption:
    """A collection that can be linked to a document."""

    key: str
    title: str
    kind: str
    item_count: int = 0

    @property
    def display_label(self) -> str:
        return self.title or self.key


@dataclass(frozen=True, slots=True)
class ProjectOption:
    """A project that can be linked to a document."""

    key: str
    title: str
    stage: str

    @property
    def display_label(self) -> str:
        return self.title or self.key


@dataclass(frozen=True, slots=True)
class LinkingResult:
    """Outcome of a link operation."""

    document_key: str
    target: LinkTarget
    target_key: str
    linked: bool
    message: str = ""
    affected: int = 0


@dataclass(frozen=True, slots=True)
class DocumentLinkView:
    """A summary of a document's current links."""

    document_key: str
    collections: tuple[CollectionOption, ...] = field(default_factory=tuple)
    projects: tuple[ProjectOption, ...] = field(default_factory=tuple)

    @property
    def is_linked(self) -> bool:
        return bool(self.collections or self.projects)