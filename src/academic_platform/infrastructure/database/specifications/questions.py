"""Specifications for the research question repository."""

from __future__ import annotations

from academic_platform.infrastructure.database.models import ResearchQuestion
from academic_platform.infrastructure.repositories.specification import Specification


class QuestionByProject(Specification[ResearchQuestion]):
    """Matches questions belonging to a specific project."""

    def __init__(self, project_id: int) -> None:
        self._project_id = project_id

    def to_expression(self, entity: type[ResearchQuestion]):
        return entity.project_id == self._project_id


class QuestionByKind(Specification[ResearchQuestion]):
    """Matches questions of a specific kind."""

    def __init__(self, kind: str) -> None:
        self._kind = kind

    def to_expression(self, entity: type[ResearchQuestion]):
        return entity.kind == self._kind


class PrimaryQuestionForProject(Specification[ResearchQuestion]):
    """Matches the primary question of a specific project."""

    def __init__(self, project_id: int) -> None:
        self._project_id = project_id

    def to_expression(self, entity: type[ResearchQuestion]):
        return (entity.project_id == self._project_id) & (entity.is_primary == 1)