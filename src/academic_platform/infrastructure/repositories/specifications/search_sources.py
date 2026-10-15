"""Specifications for the search source repository."""

from __future__ import annotations

from academic_platform.infrastructure.database.models import SearchSource
from academic_platform.infrastructure.repositories.specification import Specification


class SearchSourceEnabled(Specification[SearchSource]):
    """Matches enabled search sources."""

    def to_expression(self, entity: type[SearchSource]):
        return entity.enabled == 1


class SearchSourceByType(Specification[SearchSource]):
    """Matches search sources of a specific type."""

    def __init__(self, source_type: str) -> None:
        self._type = source_type

    def to_expression(self, entity: type[SearchSource]):
        return entity.source_type == self._type