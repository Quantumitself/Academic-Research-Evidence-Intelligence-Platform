"""Research Plan section.

The section captures the structured research plan. The plan is composed
of named fields the user edits; the section reports which fields are
populated so the page's navigation sidebar reflects the plan's state.
"""

from __future__ import annotations

from PySide6.QtWidgets import QVBoxLayout, QWidget

from academic_platform.ui.pages.research_assistant.section_base import (
    AssistantSection,
    AssistantSectionId,
)
from academic_platform.ui.pages.research_assistant.sections._shared import (
    make_multiline_field,
)

_PLAN_FIELDS: tuple[tuple[str, str, str], ...] = (
    ("background", "Background", "The background to the study."),
    ("problem_statement", "Problem statement", "The problem the study addresses."),
    ("research_question", "Research question", "The primary research question."),
    ("objectives", "Objectives", "What the study aims to achieve."),
    ("design", "Design", "The research design."),
    ("population", "Population", "The population and setting."),
    ("sampling", "Sampling", "The sampling strategy."),
    ("data_collection", "Data collection", "How data will be collected."),
    ("analysis", "Analysis", "How data will be analyzed."),
    ("ethics", "Ethics", "Ethical considerations."),
    ("limitations", "Limitations", "Anticipated limitations."),
    ("references", "References", "Key references."),
    ("open_questions", "Open questions", "Decisions still to be made."),
)


class ResearchPlanSection(AssistantSection):
    """Research Plan section."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(AssistantSectionId.RESEARCH_PLAN, parent=parent)

        content = QWidget(self)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        self._fields: dict[str, object] = {}
        for key, label, placeholder in _PLAN_FIELDS:
            editor = make_multiline_field(
                content,
                label,
                placeholder=placeholder,
                minimum_height=90,
            )
            self._fields[key] = editor

        self._install_content(content)

    # ------------------------------------------------------------------
    # Contract
    # ------------------------------------------------------------------
    def field_value(self, key: str) -> str:
        editor = self._fields.get(key)
        if editor is None:
            return ""
        return editor.toPlainText().strip()  # type: ignore[attr-defined]

    def populated_fields(self) -> list[str]:
        return [
            key
            for key in self._fields.keys()
            if self.field_value(key)
        ]

    def summary(self) -> str:
        populated = self.populated_fields()
        if not populated:
            return ""
        return f"{len(populated)} / {len(self._fields)} field(s) populated"

    def reset(self) -> None:
        for editor in self._fields.values():
            editor.setPlainText("")  # type: ignore[attr-defined]