"""Specifications for the collection repository."""

from __future__ import annotations

from academic_platform.infrastructure.database.models import Collection
from academic_platform.infrastructure.repositories.specification import Specification


class CollectionByKind(Specification[Collection]):
    """Matches collections of a specific kind."""

    def __init__(self, kind: str) -> None:
        self._kind = kind

    def to_expression(self, entity: type[Collection]):
        return entity.kind == self._kind


class CollectionByProject(Specification[Collection]):
    """Matches collections linked to a specific project."""

    def __init__(self, project_id: int) -> None:
        self._project_id = project_id

    def to_expression(self, entity: type[Collection]):
        return entity.project_id == self._project_id