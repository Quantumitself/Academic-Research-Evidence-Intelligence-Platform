"""Statistical Analysis Advisor section.

The section captures the data the user expects to analyze and a list of
candidate statistical methods. Rule-based recommendations are delivered
in a later phase; the section captures the inputs and the selection.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
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
    ("descriptive", "Descriptive statistics"),
    ("t_test_independent", "Independent-samples t-test"),
    ("t_test_paired", "Paired-samples t-test"),
    ("anova", "ANOVA"),
    ("repeated_measures", "Repeated-measures ANOVA"),
    ("mann_whitney", "Mann–Whitney U"),
    ("wilcoxon", "Wilcoxon signed-rank"),
    ("kruskal_wallis", "Kruskal–Wallis"),
    ("chi_square", "Chi-square test"),
    ("pearson", "Pearson correlation"),
    ("spearman", "Spearman correlation"),
    ("linear_regression", "Linear regression"),
    ("logistic_regression", "Logistic regression"),
    ("poisson", "Poisson regression"),
    ("negative_binomial", "Negative-binomial regression"),
    ("mixed_effects", "Mixed-effects model"),
    ("multilevel", "Multilevel model"),
    ("reliability", "Reliability estimate"),
    ("efa", "Exploratory factor analysis"),
    ("cfa", "Confirmatory factor analysis"),
    ("survival", "Survival analysis"),
    ("cox", "Cox regression"),
    ("thematic", "Thematic analysis"),
    ("effect_size", "Effect-size calculation"),
    ("meta_analysis", "Meta-analysis"),
    ("other", "Other"),
)


class StatisticalAdvisorSection(AssistantSection):
    """Statistical Analysis Advisor section."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(
            AssistantSectionId.STATISTICAL_ADVISOR, parent=parent
        )

        content = QWidget(self)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        self._data_notes = make_multiline_field(
            content,
            "Data description",
            placeholder=(
                "Outcome variable, predictors, measurement scales, groups, "
                "and expected sample size."
            ),
            minimum_height=120,
        )

        self._assumptions = make_multiline_field(
            content,
            "Assumptions and diagnostics",
            placeholder=(
                "Distributional assumptions, independence, missing data, "
                "and diagnostics to run."
            ),
            minimum_height=100,
        )

        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(6)

        self._method_combo = QComboBox(content)
        self._method_combo.setObjectName("statisticalMethod")
        for identifier, label in _CANDIDATE_METHODS:
            self._method_combo.addItem(label, identifier)
        actions.addWidget(self._method_combo, 1)

        self._add_button = QPushButton("Add candidate", content)
        self._add_button.setObjectName("statisticalAddCandidate")
        self._add_button.setAutoDefault(False)
        self._add_button.clicked.connect(self._on_add_candidate)
        actions.addWidget(self._add_button)

        layout.addLayout(actions)

        self._candidates = QListWidget(content)
        self._candidates.setObjectName("statisticalCandidateList")
        self._candidates.currentItemChanged.connect(self._on_candidate_selected)
        layout.addWidget(self._candidates, 1)

        candidate_actions = QHBoxLayout()
        candidate_actions.setContentsMargins(0, 0, 0, 0)
        candidate_actions.setSpacing(6)

        self._choose_button = QPushButton("Mark as chosen", content)
        self._choose_button.setObjectName("statisticalChooseCandidate")
        self._choose_button.setAutoDefault(False)
        self._choose_button.setEnabled(False)
        self._choose_button.clicked.connect(self._on_choose_candidate)
        candidate_actions.addWidget(self._choose_button)

        self._remove_button = QPushButton("Remove", content)
        self._remove_button.setObjectName("statisticalRemoveCandidate")
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
            f"Remove the method {item.text()!r}?",
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

    def chosen_method(self) -> str | None:
        for candidate in self.candidates():
            if candidate.get("chosen"):
                return candidate.get("identifier")
        return None

    def data_notes(self) -> str:
        return self._data_notes.toPlainText().strip()

    def assumptions(self) -> str:
        return self._assumptions.toPlainText().strip()

    def summary(self) -> str:
        candidates = self.candidates()
        if not candidates and not self.data_notes():
            return ""
        parts: list[str] = []
        if self.data_notes():
            parts.append("data notes set")
        if candidates:
            parts.append(f"{len(candidates)} candidate(s)")
        if self.chosen_method():
            parts.append("chosen")
        return " · ".join(parts)

    def reset(self) -> None:
        self._data_notes.setPlainText("")
        self._assumptions.setPlainText("")
        self._candidates.clear()