"""Value objects for the research project service."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ProjectStage(str, Enum):
    """Lifecycle stages for a research project."""

    IDEA = "idea"
    DESIGN = "design"
    COLLECTION = "collection"
    ANALYSIS = "analysis"
    WRITING = "writing"
    COMPLETE = "complete"
    ARCHIVED = "archived"

    @property
    def display_name(self) -> str:
        return {
            ProjectStage.IDEA: "Idea",
            ProjectStage.DESIGN: "Design",
            ProjectStage.COLLECTION: "Collection",
            ProjectStage.ANALYSIS: "Analysis",
            ProjectStage.WRITING: "Writing",
            ProjectStage.COMPLETE: "Complete",
            ProjectStage.ARCHIVED: "Archived",
        }[self]


@dataclass(frozen=True, slots=True)
class ProjectQuestionView:
    """A research question as seen by the presentation layer."""

    identifier: int
    text: str
    kind: str
    is_primary: bool
    position: int
    created_at: str
    updated_at: str

    @property
    def display_label(self) -> str:
        prefix = "★ " if self.is_primary else ""
        return f"{prefix}{self.text}"


@dataclass(frozen=True, slots=True)
class ProjectTaskView:
    """A research task as seen by the presentation layer."""

    identifier: int
    title: str
    description: str
    completed: bool
    position: int
    due_at: str | None
    created_at: str
    updated_at: str

    @property
    def display_label(self) -> str:
        return ("✓ " if self.completed else "• ") + self.title


@dataclass(frozen=True, slots=True)
class ProjectView:
    """A project as seen by the presentation layer."""

    identifier: int
    key: str
    title: str
    topic: str
    stage: ProjectStage
    created_at: str
    updated_at: str
    version: int
    question_count: int = 0
    open_task_count: int = 0
    total_task_count: int = 0
    document_count: int = 0
    questions: tuple[ProjectQuestionView, ...] = field(default_factory=tuple)

    @property
    def display_label(self) -> str:
        return self.title or self.key

    @property
    def completion_ratio(self) -> float:
        if self.total_task_count <= 0:
            return 0.0
        completed = self.total_task_count - self.open_task_count
        return max(0.0, min(1.0, completed / self.total_task_count))