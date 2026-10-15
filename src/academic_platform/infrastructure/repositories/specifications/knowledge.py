"""Specifications for the knowledge, guide, achievement, and plan repositories."""

from __future__ import annotations

from academic_platform.infrastructure.database.models import (
    Achievement,
    KnowledgeNode,
    KnowledgeRelationship,
    ResearchGuide,
    ResearchGuideSection,
    ResearchPlan,
    ResearchTask,
)
from academic_platform.infrastructure.repositories.specification import Specification


class KnowledgeNodeByKind(Specification[KnowledgeNode]):
    """Matches knowledge nodes of a specific kind."""

    def __init__(self, kind: str) -> None:
        self._kind = kind

    def to_expression(self, entity: type[KnowledgeNode]):
        return entity.node_kind == self._kind


class KnowledgeRelationshipFrom(Specification[KnowledgeRelationship]):
    """Matches relationships whose source is a specific node."""

    def __init__(self, source_node_id: int) -> None:
        self._source = source_node_id

    def to_expression(self, entity: type[KnowledgeRelationship]):
        return entity.source_node_id == self._source


class KnowledgeRelationshipTo(Specification[KnowledgeRelationship]):
    """Matches relationships whose target is a specific node."""

    def __init__(self, target_node_id: int) -> None:
        self._target = target_node_id

    def to_expression(self, entity: type[KnowledgeRelationship]):
        return entity.target_node_id == self._target


class KnowledgeRelationshipAIGrounded(Specification[KnowledgeRelationship]):
    """Matches relationships proposed by AI that await review."""

    def to_expression(self, entity: type[KnowledgeRelationship]):
        return entity.grounding == "ai_proposed"


class ResearchGuideByKind(Specification[ResearchGuide]):
    """Matches guides of a specific kind."""

    def __init__(self, kind: str) -> None:
        self._kind = kind

    def to_expression(self, entity: type[ResearchGuide]):
        return entity.guide_kind == self._kind


class ResearchGuideForProject(Specification[ResearchGuide]):
    """Matches guides owned by a specific project."""

    def __init__(self, project_id: int) -> None:
        self._project_id = project_id

    def to_expression(self, entity: type[ResearchGuide]):
        return entity.project_id == self._project_id


class ResearchGuideSectionFor(Specification[ResearchGuideSection]):
    """Matches sections belonging to a specific guide."""

    def __init__(self, guide_id: int) -> None:
        self._guide_id = guide_id

    def to_expression(self, entity: type[ResearchGuideSection]):
        return entity.guide_id == self._guide_id


class AchievementActive(Specification[Achievement]):
    """Matches active achievements."""

    def to_expression(self, entity: type[Achievement]):
        return entity.active == 1


class ResearchPlanForProject(Specification[ResearchPlan]):
    """Matches research plans owned by a specific project."""

    def __init__(self, project_id: int) -> None:
        self._project_id = project_id

    def to_expression(self, entity: type[ResearchPlan]):
        return entity.project_id == self._project_id


class ResearchTaskForProject(Specification[ResearchTask]):
    """Matches tasks belonging to a specific project."""

    def __init__(self, project_id: int) -> None:
        self._project_id = project_id

    def to_expression(self, entity: type[ResearchTask]):
        return entity.project_id == self._project_id


class ResearchTaskOpen(Specification[ResearchTask]):
    """Matches tasks that are not yet complete."""

    def to_expression(self, entity: type[ResearchTask]):
        return entity.completed == 0