"""Specifications for the research project repository."""

from __future__ import annotations

from academic_platform.infrastructure.database.models import ResearchProject
from academic_platform.infrastructure.repositories.specification import Specification


class ProjectByStage(Specification[ResearchProject]):
    """Matches projects at a specific lifecycle stage."""

    def __init__(self, stage: str) -> None:
        self._stage = stage

    def to_expression(self, entity: type[ResearchProject]):
        return entity.stage == self._stage


class ProjectTitleContains(Specification[ResearchProject]):
    """Matches projects whose title contains a substring (case-insensitive)."""

    def __init__(self, fragment: str) -> None:
        self._fragment = fragment.lower()

    def to_expression(self, entity: type[ResearchProject]):
        # SQLite's LIKE is case-insensitive for ASCII by default. The
        # lower() call on the fragment matches the user's intent for
        # ASCII input; non-ASCII case folding is deferred to a future
        # phase that can afford ICU collation.
        return entity.title.ilike(f"%{self._fragment}%")