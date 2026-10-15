"""Reusable search bar.

The bar composes a text input, an optional scope selector, a submit button,
and a clear button. It emits signals describing the user's intent; it does
not execute searches.

Design decisions
----------------
- The submit signal carries the current text and the current scope. Both are
  always present; the scope is an empty string when no scope selector is
  configured.
- The clear signal is emitted regardless of whether the input was empty, so
  callers can reset dependent state unconditionally.
- Pressing Enter in the input submits; pressing Escape clears.
- When a scope selector is configured, the caller supplies the initial list
  of scopes and their labels.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QWidget,
)

class _SearchInput(QLineEdit):
    """QLineEdit that emits ``escape_pressed`` on Escape."""

    escape_pressed = Signal()

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802 - Qt API
        if event.key() == Qt.Key.Key_Escape:
            self.escape_pressed.emit()
            event.accept()
            return
        super().keyPressEvent(event)

class SearchBar(QWidget):
    """Search input with optional scope selector and submit/clear actions."""

    submitted = Signal(str, str)
    cleared = Signal()
    scope_changed = Signal(str)
    text_changed = Signal(str)

    def __init__(
        self,
        *,
        placeholder: str = "Search…",
        scopes: tuple[tuple[str, str], ...] = (),
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("searchBar")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self._scope_combo: QComboBox | None = None
        if scopes:
            self._scope_combo = QComboBox(self)
            self._scope_combo.setObjectName("searchBarScope")
            for identifier, label in scopes:
                self._scope_combo.addItem(label, identifier)
            self._scope_combo.currentIndexChanged.connect(self._on_scope_changed)
            layout.addWidget(self._scope_combo)

        self._input = _SearchInput(self)
        self._input.escape_pressed.connect(self._on_clear)
        self._input.setObjectName("searchBarInput")
        self._input.setPlaceholderText(placeholder)
        self._input.setClearButtonEnabled(False)
        self._input.returnPressed.connect(self._on_submit)
        self._input.textChanged.connect(self.text_changed.emit)
        layout.addWidget(self._input, 1)

        self._submit_button = QPushButton("Search", self)
        self._submit_button.setObjectName("searchBarSubmit")
        self._submit_button.setDefault(False)
        self._submit_button.setAutoDefault(False)
        self._submit_button.clicked.connect(self._on_submit)
        layout.addWidget(self._submit_button)

        self._clear_button = QPushButton("Clear", self)
        self._clear_button.setObjectName("searchBarClear")
        self._clear_button.setAutoDefault(False)
        self._clear_button.clicked.connect(self._on_clear)
        layout.addWidget(self._clear_button)


    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def text(self) -> str:
        """Return the current input text."""
        return self._input.text()

    def set_text(self, text: str) -> None:
        """Replace the input text without emitting ``submitted``."""
        self._input.setText(text)

    def scope(self) -> str:
        """Return the current scope identifier, or an empty string."""
        if self._scope_combo is None:
            return ""
        data = self._scope_combo.currentData()
        return str(data) if data is not None else ""

    def set_scope(self, identifier: str) -> None:
        """Select the scope with the given identifier. No-op if unknown."""
        if self._scope_combo is None:
            return
        for index in range(self._scope_combo.count()):
            if self._scope_combo.itemData(index) == identifier:
                self._scope_combo.setCurrentIndex(index)
                return

    def set_placeholder(self, placeholder: str) -> None:
        """Replace the placeholder text."""
        self._input.setPlaceholderText(placeholder)

    def set_enabled(self, enabled: bool) -> None:
        """Enable or disable the whole bar."""
        self._input.setEnabled(enabled)
        self._submit_button.setEnabled(enabled)
        self._clear_button.setEnabled(enabled)
        if self._scope_combo is not None:
            self._scope_combo.setEnabled(enabled)

    def focus_input(self) -> None:
        """Move keyboard focus to the input field."""
        self._input.setFocus(Qt.FocusReason.ShortcutFocusReason)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------
    def _on_submit(self) -> None:
        self.submitted.emit(self._input.text(), self.scope())

    def _on_clear(self) -> None:
        self._input.clear()
        self.cleared.emit()

    def _on_scope_changed(self, _index: int) -> None:
        self.scope_changed.emit(self.scope())