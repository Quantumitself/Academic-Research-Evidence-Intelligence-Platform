"""Methodology Advisor section.

The section is a workspace for comparing candidate methodologies. The
user adds a methodology, records its strengths, limitations, and
assumptions, and marks it as chosen. Rule-based recommendations are
delivered in a later phase.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from academic_platform.ui.dialogs.confirm_dialog import ConfirmResult
from academic_platform.ui.dialogs.dialog_factory import DialogFactory
from academic_platform.ui.pages.research_assistant.section_base import (
    AssistantSection,
    AssistantSectionId,
)
from academic_platform.ui.pages.research_assistant.sections._shared import (
    make_multiline_field,
)

_CANDIDATE_METHODS: tuple[tuple[str, str], ...] = (
    ("experiment", "Experimental research"),
    ("rct", "Randomized controlled study"),
    ("quasi_experimental", "Quasi-experimental design"),
    ("cross_sectional", "Cross-sectional study"),
    ("longitudinal", "Longitudinal study"),
    ("cohort", "Cohort study"),
    ("case_control", "Case-control study"),
    ("survey", "Survey research"),
    ("correlational", "Correlational research"),
    ("interview", "Qualitative interviews"),
    ("focus_group", "Focus groups"),
    ("case_study", "Case study"),
    ("ethnography", "Ethnographic research"),
    ("mixed_methods", "Mixed-methods design"),
    ("systematic_review", "Systematic review"),
    ("scoping_review", "Scoping review"),
    ("meta_analysis", "Meta-analysis"),
    ("theoretical", "Theoretical or conceptual research"),
    ("secondary_data", "Secondary-data analysis"),
    ("other", "Other"),
)


class MethodologySection(AssistantSection):
    """Methodology Advisor section."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(AssistantSectionId.METHODOLOGY, parent=parent)

        content = QWidget(self)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        self._rationale = make_multiline_field(
            content,
            "Rationale notes",
            placeholder=(
                "Why might this methodology be appropriate to the research "
                "question?"
            ),
            minimum_height=120,
        )

        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(6)

        self._method_combo = QComboBox(content)
        self._method_combo.setObjectName("methodologyMethod")
        for identifier, label in _CANDIDATE_METHODS:
            self._method_combo.addItem(label, identifier)
        actions.addWidget(self._method_combo, 1)

        self._add_button = QPushButton("Add candidate", content)
        self._add_button.setObjectName("methodologyAddCandidate")
        self._add_button.setAutoDefault(False)
        self._add_button.clicked.connect(self._on_add_candidate)
        actions.addWidget(self._add_button)

        layout.addLayout(actions)

        self._candidates = QListWidget(content)
        self._candidates.setObjectName("methodologyCandidateList")
        self._candidates.currentItemChanged.connect(self._on_candidate_selected)
        layout.addWidget(self._candidates, 1)

        candidate_actions = QHBoxLayout()
        candidate_actions.setContentsMargins(0, 0, 0, 0)
        candidate_actions.setSpacing(6)

        self._choose_button = QPushButton("Mark as chosen", content)
        self._choose_button.setObjectName("methodologyChooseCandidate")
        self._choose_button.setAutoDefault(False)
        self._choose_button.setEnabled(False)
        self._choose_button.clicked.connect(self._on_choose_candidate)
        candidate_actions.addWidget(self._choose_button)

        self._remove_button = QPushButton("Remove", content)
        self._remove_button.setObjectName("methodologyRemoveCandidate")
        self._remove_button.setAutoDefault(False)
        self._remove_button.setEnabled(False)
        self._remove_button.clicked.connect(self._on_remove_candidate)
        candidate_actions.addWidget(self._remove_button)

        candidate_actions.addStretch(1)
        layout.addLayout(candidate_actions)

        self._install_content(content)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------
    def _on_add_candidate(self) -> None:
        identifier = self._method_combo.currentData()
        label = self._method_combo.currentText()
        if not identifier:
            return
        for index in range(self._candidates.count()):
            existing = self._candidates.item(index).data(
                Qt.ItemDataRole.UserRole
            )
            if isinstance(existing, dict) and existing.get("identifier") == identifier:
                return
        item = QListWidgetItem(label, self._candidates)
        item.setData(
            Qt.ItemDataRole.UserRole,
            {"identifier": identifier, "label": label, "chosen": False},
        )
        self._candidates.addItem(item)

    def _on_candidate_selected(
        self,
        current: QListWidgetItem | None,
        _previous: QListWidgetItem | None,
    ) -> None:
        enabled = current is not None
        self._choose_button.setEnabled(enabled)
        self._remove_button.setEnabled(enabled)

    def _on_choose_candidate(self) -> None:
        current = self._candidates.currentItem()
        if current is None:
            return
        for index in range(self._candidates.count()):
            item = self._candidates.item(index)
            data = item.data(Qt.ItemDataRole.UserRole)
            if not isinstance(data, dict):
                continue
            data = dict(data)
            data["chosen"] = item is current
            item.setData(Qt.ItemDataRole.UserRole, data)
            item.setText(("★ " if data["chosen"] else "") + data["label"])

    def _on_remove_candidate(self) -> None:
        item = self._candidates.currentItem()
        if item is None:
            return
        outcome = DialogFactory.confirm(
            self,
            "Remove candidate",
            f"Remove the methodology {item.text()!r}?",
            confirm_label="Remove",
            cancel_label="Cancel",
            destructive=True,
            default_to_confirm=False,
        )
        if outcome.result is not ConfirmResult.CONFIRMED:
            return
        self._candidates.takeItem(self._candidates.row(item))

    # ------------------------------------------------------------------
    # Contract
    # ------------------------------------------------------------------
    def candidates(self) -> list[dict]:
        results: list[dict] = []
        for index in range(self._candidates.count()):
            data = self._candidates.item(index).data(Qt.ItemDataRole.UserRole)
            if isinstance(data, dict):
                results.append(data)
        return results

    def chosen_methodology(self) -> str | None:
        for candidate in self.candidates():
            if candidate.get("chosen"):
                return candidate.get("identifier")
        return None

    def rationale(self) -> str:
        return self._rationale.toPlainText().strip()

    def summary(self) -> str:
        candidates = self.candidates()
        chosen = self.chosen_methodology()
        if not candidates:
            return ""
        parts: list[str] = [f"{len(candidates)} candidate(s)"]
        if chosen:
            parts.append("chosen")
        return " · ".join(parts)

    def reset(self) -> None:
        self._rationale.setPlainText("")
        self._candidates.clear()