"""Label/value metadata grid.

Renders a set of (label, value) rows in a two-column grid. Values may be
plain text or clickable links. Link clicks are emitted as
``link_activated(key, value)`` so that the caller decides how to open the
target. The component never opens URLs itself.

Design decisions
----------------
- Rows are added through ``add_row`` and may be updated with ``set_value``.
  The order of rows is preserved.
- Empty values are hidden rather than rendered blank, so that the grid
  does not present placeholder rows that carry no information.
- Long values wrap within the value column; the label column is fixed at a
  width chosen by the first row's hint.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QLabel,
    QPushButton,
    QWidget,
)


class MetadataGrid(QFrame):
    """Two-column label/value grid."""

    link_activated = Signal(str, str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("metadataGrid")
        self.setFrameShape(QFrame.Shape.NoFrame)

        self._layout = QGridLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setHorizontalSpacing(12)
        self._layout.setVerticalSpacing(6)
        self._layout.setColumnStretch(0, 0)
        self._layout.setColumnStretch(1, 1)

        self._label_widgets: dict[str, QLabel] = {}
        self._value_widgets: dict[str, QLabel] = {}
        self._link_widgets: dict[str, QPushButton] = {}
        self._row_count = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def add_row(self, key: str, label: str, value: str, *, link: bool = False) -> None:
        """Add a row. If ``link`` is True, the value is rendered as a button."""
        if key in self._label_widgets:
            raise KeyError(f"Metadata row already exists: {key}")

        label_widget = QLabel(label, self)
        label_widget.setObjectName("metadataGridLabel")
        label_widget.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self._layout.addWidget(label_widget, self._row_count, 0)
        self._label_widgets[key] = label_widget

        if link:
            value_widget: QWidget = QPushButton(value, self)
            value_widget.setObjectName("metadataGridLink")
            value_widget.setFlat(True)
            value_widget.setAutoDefault(False)
            value_widget.setCursor(Qt.CursorShape.PointingHandCursor)
            value_widget.clicked.connect(  # type: ignore[attr-defined]
                lambda _checked=False, k=key: self.link_activated.emit(k, self._link_value(k))
            )
            self._link_widgets[key] = value_widget  # type: ignore[assignment]
        else:
            value_widget = QLabel(value, self)
            value_widget.setObjectName("metadataGridValue")
            value_widget.setWordWrap(True)
            value_widget.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse
            )
            self._value_widgets[key] = value_widget  # type: ignore[assignment]

        self._layout.addWidget(value_widget, self._row_count, 1)
        self._row_count += 1
        self._apply_visibility(key, value)

    def set_value(self, key: str, value: str) -> None:
        """Replace the value of an existing row."""
        if key in self._link_widgets:
            self._link_widgets[key].setText(value)
        elif key in self._value_widgets:
            self._value_widgets[key].setText(value)
        else:
            raise KeyError(f"Unknown metadata row: {key}")
        self._apply_visibility(key, value)

    def set_label(self, key: str, label: str) -> None:
        """Replace the label of an existing row."""
        if key not in self._label_widgets:
            raise KeyError(f"Unknown metadata row: {key}")
        self._label_widgets[key].setText(label)

    def value(self, key: str) -> str:
        """Return the current value of a row, or an empty string if absent."""
        if key in self._link_widgets:
            return self._link_widgets[key].text()
        if key in self._value_widgets:
            return self._value_widgets[key].text()
        return ""

    def remove_row(self, key: str) -> None:
        """Remove a row. No-op if the key is unknown."""
        label = self._label_widgets.pop(key, None)
        value = self._value_widgets.pop(key, None) or self._link_widgets.pop(key, None)
        if label is not None:
            self._layout.removeWidget(label)
            label.setParent(None)
            label.deleteLater()
        if value is not None:
            self._layout.removeWidget(value)
            value.setParent(None)
            value.deleteLater()

    def clear(self) -> None:
        """Remove all rows."""
        for key in list(self._label_widgets.keys()):
            self.remove_row(key)
        self._row_count = 0

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _link_value(self, key: str) -> str:
        widget = self._link_widgets.get(key)
        return widget.text() if widget is not None else ""

    def _apply_visibility(self, key: str, value: str) -> None:
        visible = bool(value.strip())
        self._label_widgets[key].setVisible(visible)
        if key in self._link_widgets:
            self._link_widgets[key].setVisible(visible)
        elif key in self._value_widgets:
            self._value_widgets[key].setVisible(visible)