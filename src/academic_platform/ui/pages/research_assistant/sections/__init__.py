"""Research assistant sections.

Each section is a self-contained widget. The ``create_section`` factory
maps a section identifier to a concrete instance so that the page does
not need to know which module implements which section.
"""

from __future__ import annotations

from PySide6.QtWidgets import QWidget

from academic_platform.ui.pages.research_assistant.section_base import (
    AssistantSection,
    AssistantSectionId,
)
from academic_platform.ui.pages.research_assistant.sections.methodology_section import (
    MethodologySection,
)
from academic_platform.ui.pages.research_assistant.sections.plan_section import (
    ResearchPlanSection,
)
from academic_platform.ui.pages.research_assistant.sections.questions_section import (
    ResearchQuestionsSection,
)
from academic_platform.ui.pages.research_assistant.sections.review_section import (
    ReviewSection,
)
from academic_platform.ui.pages.research_assistant.sections.sources_section import (
    SourcesSection,
)
from academic_platform.ui.pages.research_assistant.sections.statistical_section import (
    StatisticalAdvisorSection,
)
from academic_platform.ui.pages.research_assistant.sections.theories_section import (
    TheoriesSection,
)
from academic_platform.ui.pages.research_assistant.sections.title_section import (
    TitleBuilderSection,
)
from academic_platform.ui.pages.research_assistant.sections.topic_section import (
    TopicSection,
)
from academic_platform.ui.pages.research_assistant.sections.history_section import (
    ResearchHistorySection,
)

__all__ = [
    "MethodologySection",
    "ResearchHistorySection",
    "ResearchPlanSection",
    "ResearchQuestionsSection",
    "ReviewSection",
    "SourcesSection",
    "StatisticalAdvisorSection",
    "TheoriesSection",
    "TitleBuilderSection",
    "TopicSection",
    "create_section",
]


_SECTION_CLASSES: dict[AssistantSectionId, type[AssistantSection]] = {
    AssistantSectionId.TOPIC: TopicSection,
    AssistantSectionId.TITLE_BUILDER: TitleBuilderSection,
    AssistantSectionId.RESEARCH_HISTORY: ResearchHistorySection,
    AssistantSectionId.RESEARCH_QUESTIONS: ResearchQuestionsSection,
    AssistantSectionId.THEORIES: TheoriesSection,
    AssistantSectionId.METHODOLOGY: MethodologySection,
    AssistantSectionId.STATISTICAL_ADVISOR: StatisticalAdvisorSection,
    AssistantSectionId.RESEARCH_PLAN: ResearchPlanSection,
    AssistantSectionId.SOURCES: SourcesSection,
    AssistantSectionId.REVIEW: ReviewSection,
}


def create_section(
    section_id: AssistantSectionId,
    parent: QWidget | None = None,
) -> AssistantSection:
    """Construct the section for the given identifier."""
    section_class = _SECTION_CLASSES.get(section_id)
    if section_class is None:
        raise KeyError(f"Unknown research assistant section: {section_id!r}")
    return section_class(parent=parent)