"""Theories & Concepts section.

The section captures the theories, concepts, and constructs the study
relies on. Each entry carries a name and an optional definition.
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


class TheoriesSection(AssistantSection):
    """Theories & Concepts section."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(AssistantSectionId.THEORIES, parent=parent)

        content = QWidget(self)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        self._narrative = make_multiline_field(
            content,
            "Theoretical framework notes",
            placeholder=(
                "How do the theories relate to each other and to the "
                "research question?"
            ),
            minimum_height=120,
        )

        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(6)

        self._name_input = QLineEdit(content)
        self._name_input.setObjectName("theoriesNameInput")
        self._name_input.setPlaceholderText("Theory or concept name…")
        actions.addWidget(self._name_input, 1)

        self._add_button = QPushButton("Add", content)
        self._add_button.setObjectName("theoriesAddEntry")
        self._add_button.setAutoDefault(False)
        self._add_button.clicked.connect(self._on_add_entry)
        actions.addWidget(self._add_button)

        layout.addLayout(actions)

        self._entries = QListWidget(content)
        self._entries.setObjectName("theoriesEntryList")
        self._entries.currentItemChanged.connect(self._on_entry_selected)
        layout.addWidget(self._entries, 1)

        remove_row = QHBoxLayout()
        remove_row.setContentsMargins(0, 0, 0, 0)
        remove_row.setSpacing(6)

        self._remove_button = QPushButton("Remove", content)
        self._remove_button.setObjectName("theoriesRemoveEntry")
        self._remove_button.setAutoDefault(False)
        self._remove_button.setEnabled(False)
        self._remove_button.clicked.connect(self._on_remove_entry)
        remove_row.addWidget(self._remove_button)

        remove_row.addStretch(1)
        layout.addLayout(remove_row)

        self._install_content(content)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------
    def _on_add_entry(self) -> None:
        text = self._name_input.text().strip()
        if not text:
            return
        item = QListWidgetItem(text, self._entries)
        item.setData(Qt.ItemDataRole.UserRole, text)
        self._entries.addItem(item)
        self._name_input.clear()

    def _on_entry_selected(
        self,
        current: QListWidgetItem | None,
        _previous: QListWidgetItem | None,
    ) -> None:
        self._remove_button.setEnabled(current is not None)

    def _on_remove_entry(self) -> None:
        item = self._entries.currentItem()
        if item is None:
            return
        outcome = DialogFactory.confirm(
            self,
            "Remove entry",
            f"Remove {item.text()!r}?",
            confirm_label="Remove",
            cancel_label="Cancel",
            destructive=True,
            default_to_confirm=False,
        )
        if outcome.result is not ConfirmResult.CONFIRMED:
            return
        self._entries.takeItem(self._entries.row(item))

    # ------------------------------------------------------------------
    # Contract
    # ------------------------------------------------------------------
    def entries(self) -> list[str]:
        return [
            self._entries.item(index).text()
            for index in range(self._entries.count())
        ]

    def narrative(self) -> str:
        return self._narrative.toPlainText().strip()

    def summary(self) -> str:
        count = self._entries.count()
        if not count and not self.narrative():
            return ""
        parts: list[str] = []
        if count:
            parts.append(f"{count} entr(y/ies)")
        if self.narrative():
            parts.append("framework notes")
        return " · ".join(parts)

    def reset(self) -> None:
        self._narrative.setPlainText("")
        self._entries.clear()