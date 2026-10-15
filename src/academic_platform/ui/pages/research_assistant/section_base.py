"""Base class and identifiers for research assistant sections.

Every section is a ``BasePage`` subclass that hosts a distinct part of
the research-design workflow. Sections participate in the page's
lifecycle: the page activates a section when the user selects it and
deactivates it when the user navigates away.

Design decisions
----------------
- A section inherits from ``BasePage`` so that it reuses the standard
  header, content stack, and empty-state contract.
- Sections expose two additional contracts on top of the base page's
  lifecycle: ``reset`` clears the section's work, and ``summary``
  returns a short status string the page's navigation sidebar renders.
- Sections never communicate with each other directly. The page
  mediates any cross-section state through its own workspace.
"""

from __future__ import annotations

from enum import Enum

from PySide6.QtWidgets import QWidget

from academic_platform.ui.pages.base_page import BasePage


class AssistantSectionId(str, Enum):
    """Stable identifiers for the research assistant's sections."""

    TOPIC = "topic"
    TITLE_BUILDER = "title_builder"
    RESEARCH_HISTORY = "research_history"
    RESEARCH_QUESTIONS = "research_questions"
    THEORIES = "theories"
    METHODOLOGY = "methodology"
    STATISTICAL_ADVISOR = "statistical_advisor"
    RESEARCH_PLAN = "research_plan"
    SOURCES = "sources"
    REVIEW = "review"

    @property
    def display_name(self) -> str:
        return {
            AssistantSectionId.TOPIC: "Topic & Problem",
            AssistantSectionId.TITLE_BUILDER: "Title Builder",
            AssistantSectionId.RESEARCH_HISTORY: "Research History",
            AssistantSectionId.RESEARCH_QUESTIONS: "Research Questions",
            AssistantSectionId.THEORIES: "Theories & Concepts",
            AssistantSectionId.METHODOLOGY: "Methodology Advisor",
            AssistantSectionId.STATISTICAL_ADVISOR: "Statistical Analysis",
            AssistantSectionId.RESEARCH_PLAN: "Research Plan",
            AssistantSectionId.SOURCES: "Sources & Evidence",
            AssistantSectionId.REVIEW: "Review & Export",
        }[self]

    @property
    def description(self) -> str:
        return {
            AssistantSectionId.TOPIC: (
                "Clarify the broad subject, the research problem, and the "
                "context."
            ),
            AssistantSectionId.TITLE_BUILDER: (
                "Generate and compare candidate research titles."
            ),
            AssistantSectionId.RESEARCH_HISTORY: (
                "Map how the topic has developed over time."
            ),
            AssistantSectionId.RESEARCH_QUESTIONS: (
                "Develop and refine the research question."
            ),
            AssistantSectionId.THEORIES: (
                "Collect the theories and concepts the study relies on."
            ),
            AssistantSectionId.METHODOLOGY: (
                "Compare plausible research methodologies."
            ),
            AssistantSectionId.STATISTICAL_ADVISOR: (
                "Identify suitable statistical analyses and their "
                "assumptions."
            ),
            AssistantSectionId.RESEARCH_PLAN: (
                "Assemble the structured research plan."
            ),
            AssistantSectionId.SOURCES: (
                "List the sources and evidence the plan relies on."
            ),
            AssistantSectionId.REVIEW: (
                "Review the plan and export the research design."
            ),
        }[self]


class AssistantSection(BasePage):
    """Base class for a research assistant section."""

    def __init__(
        self,
        section_id: AssistantSectionId,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(
            title=section_id.display_name,
            subtitle=section_id.description,
            parent=parent,
        )
        self._section_id = section_id
        self.setObjectName(f"assistantSection_{section_id.value}")

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------
    @property
    def section_id(self) -> AssistantSectionId:
        return self._section_id

    # ------------------------------------------------------------------
    # Contract
    # ------------------------------------------------------------------
    def summary(self) -> str:
        """Return a short status string for the section.

        The page's navigation sidebar renders the summary next to the
        section's name. The default implementation returns an empty
        string; sections override it to describe their state.
        """
        return ""

    def reset(self) -> None:
        """Clear the section's work.

        The default implementation is a no-op. Sections that hold
        persistent state override this method to clear it.
        """