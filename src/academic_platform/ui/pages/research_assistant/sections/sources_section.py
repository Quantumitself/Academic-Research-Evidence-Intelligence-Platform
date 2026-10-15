"""Sources & Evidence section.

The section lists the sources the plan relies on and the evidence
records the user expects to extract from them. Each source is a title
or reference string; evidence entries reference a source and carry a
short summary.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
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


class SourcesSection(AssistantSection):
    """Sources & Evidence section."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(AssistantSectionId.SOURCES, parent=parent)

        content = QWidget(self)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        source_actions = QHBoxLayout()
        source_actions.setContentsMargins(0, 0, 0, 0)
        source_actions.setSpacing(6)

        self._source_input = QLineEdit(content)
        self._source_input.setObjectName("sourcesInput")
        self._source_input.setPlaceholderText(
            "Add a source (title, DOI, URL, or document key)…"
        )
        source_actions.addWidget(self._source_input, 1)

        self._add_source_button = QPushButton("Add source", content)
        self._add_source_button.setObjectName("sourcesAddSource")
        self._add_source_button.setAutoDefault(False)
        self._add_source_button.clicked.connect(self._on_add_source)
        source_actions.addWidget(self._add_source_button)

        layout.addLayout(source_actions)

        self._sources = QListWidget(content)
        self._sources.setObjectName("sourcesList")
        self._sources.currentItemChanged.connect(self._on_source_selected)
        layout.addWidget(self._sources, 1)

        source_remove_row = QHBoxLayout()
        source_remove_row.setContentsMargins(0, 0, 0, 0)
        source_remove_row.setSpacing(6)

        self._remove_source_button = QPushButton("Remove source", content)
        self._remove_source_button.setObjectName("sourcesRemoveSource")
        self._remove_source_button.setAutoDefault(False)
        self._remove_source_button.setEnabled(False)
        self._remove_source_button.clicked.connect(self._on_remove_source)
        source_remove_row.addWidget(self._remove_source_button)

        source_remove_row.addStretch(1)
        layout.addLayout(source_remove_row)

        self._evidence_notes = make_multiline_field(
            content,
            "Evidence notes",
            placeholder=(
                "What evidence is expected from the sources above?"
            ),
            minimum_height=120,
        )

        self._install_content(content)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------
    def _on_add_source(self) -> None:
        text = self._source_input.text().strip()
        if not text:
            return
        item = QListWidgetItem(text, self._sources)
        item.setData(Qt.ItemDataRole.UserRole, text)
        self._sources.addItem(item)
        self._source_input.clear()

    def _on_source_selected(
        self,
        current: QListWidgetItem | None,
        _previous: QListWidgetItem | None,
    ) -> None:
        self._remove_source_button.setEnabled(current is not None)

    def _on_remove_source(self) -> None:
        item = self._sources.currentItem()
        if item is None:
            return
        outcome = DialogFactory.confirm(
            self,
            "Remove source",
            f"Remove the source {item.text()!r}?",
            confirm_label="Remove",
            cancel_label="Cancel",
            destructive=True,
            default_to_confirm=False,
        )
        if outcome.result is not ConfirmResult.CONFIRMED:
            return
        self._sources.takeItem(self._sources.row(item))

    # ------------------------------------------------------------------
    # Contract
    # ------------------------------------------------------------------
    def sources(self) -> list[str]:
        return [
            self._sources.item(index).text()
            for index in range(self._sources.count())
        ]

    def evidence_notes(self) -> str:
        return self._evidence_notes.toPlainText().strip()

    def summary(self) -> str:
        parts: list[str] = []
        count = self._sources.count()
        if count:
            parts.append(f"{count} source(s)")
        if self.evidence_notes():
            parts.append("evidence notes")
        return " · ".join(parts)

    def reset(self) -> None:
        self._sources.clear()
        self._evidence_notes.setPlainText("")