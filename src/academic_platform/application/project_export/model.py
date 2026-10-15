"""Value objects for project export."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ExportFormat(str, Enum):
    """Supported output formats."""

    JSON = "json"
    MARKDOWN = "markdown"

    @property
    def extension(self) -> str:
        return {
            ExportFormat.JSON: ".json",
            ExportFormat.MARKDOWN: ".md",
        }[self]

    @property
    def display_name(self) -> str:
        return {
            ExportFormat.JSON: "JSON",
            ExportFormat.MARKDOWN: "Markdown",
        }[self]


class ExportSection(str, Enum):
    """Selectable sections of the export."""

    PROJECT_FIELDS = "project_fields"
    RESEARCH_QUESTIONS = "research_questions"
    TASKS = "tasks"
    MILESTONES = "milestones"
    COLLECTIONS = "collections"
    LINKED_DOCUMENTS = "linked_documents"

    @property
    def display_name(self) -> str:
        return {
            ExportSection.PROJECT_FIELDS: "Project fields",
            ExportSection.RESEARCH_QUESTIONS: "Research questions",
            ExportSection.TASKS: "Tasks",
            ExportSection.MILESTONES: "Milestones",
            ExportSection.COLLECTIONS: "Collections",
            ExportSection.LINKED_DOCUMENTS: "Linked documents",
        }[self]


@dataclass(frozen=True, slots=True)
class ExportOptions:
    """User-selectable inclusion options for an export."""

    format: ExportFormat = ExportFormat.JSON
    sections: frozenset[ExportSection] = field(
        default_factory=lambda: frozenset(ExportSection)
    )

    @property
    def includes_project_fields(self) -> bool:
        return ExportSection.PROJECT_FIELDS in self.sections

    @property
    def includes_research_questions(self) -> bool:
        return ExportSection.RESEARCH_QUESTIONS in self.sections

    @property
    def includes_tasks(self) -> bool:
        return ExportSection.TASKS in self.sections

    @property
    def includes_milestones(self) -> bool:
        return ExportSection.MILESTONES in self.sections

    @property
    def includes_collections(self) -> bool:
        return ExportSection.COLLECTIONS in self.sections

    @property
    def includes_linked_documents(self) -> bool:
        return ExportSection.LINKED_DOCUMENTS in self.sections


@dataclass(frozen=True, slots=True)
class ExportResult:
    """Outcome of an export."""

    project_key: str
    format: ExportFormat
    output_path: str
    bytes_written: int
    sections: tuple[ExportSection, ...] = field(default_factory=tuple)

    @property
    def section_count(self) -> int:
        return len(self.sections)