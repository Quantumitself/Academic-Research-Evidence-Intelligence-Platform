"""Primary navigation sidebar.

Emits a stable destination identifier when the user selects an entry. The
widget owns no page instances and performs no navigation itself; the main
window is responsible for switching the page stack.

The bar renders each destination with an optional glyph, a label, and a
tooltip. When labels are hidden by appearance settings, the glyph remains
visible and the destination identifier is used as the accessible name.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QLabel,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from academic_platform.ui.main_window_destinations import DESTINATIONS


class NavigationBar(QWidget):
    """Sidebar navigation widget emitting ``destination_selected``."""

    destination_selected = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("navigationBar")
        self.setMinimumWidth(220)
        self.setMaximumWidth(340)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 20, 16, 20)
        layout.setSpacing(12)

        self._brand = QLabel("Research Platform", self)
        self._brand.setObjectName("navigationBrand")
        layout.addWidget(self._brand)

        self._list = QListWidget(self)
        self._list.setObjectName("navigationList")
        self._list.setUniformItemSizes(True)
        self._list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self._list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._list.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)

        for destination in DESTINATIONS:
            item = QListWidgetItem(self._list)
            item.setData(Qt.ItemDataRole.UserRole, destination.identifier)
            item.setText(self._render_label(destination.glyph, destination.label))
            item.setToolTip(destination.purpose)
        layout.addWidget(self._list, 1)

        self._footer = QLabel("Local-first research workspace", self)
        self._footer.setObjectName("navigationFooter")
        self._footer.setWordWrap(True)
        layout.addWidget(self._footer)

        self._labels_visible = True
        self._list.currentItemChanged.connect(self._on_current_item_changed)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def select(self, identifier: str) -> None:
        """Programmatically select a destination by identifier.

        Emits ``destination_selected`` if the selection actually changes.
        """
        for index in range(self._list.count()):
            item = self._list.item(index)
            if item.data(Qt.ItemDataRole.UserRole) == identifier:
                self._list.setCurrentItem(item)
                return

    def set_labels_visible(self, visible: bool) -> None:
        """Show or hide textual labels.

        When labels are hidden, the glyph remains visible and the accessible
        name is set to the destination label so that assistive technologies
        can still announce the destination.
        """
        self._labels_visible = visible
        for index in range(self._list.count()):
            item = self._list.item(index)
            identifier = item.data(Qt.ItemDataRole.UserRole)
            destination = next(
                (dest for dest in DESTINATIONS if dest.identifier == identifier),
                None,
            )
            if destination is None:
                continue
            if visible:
                item.setText(self._render_label(destination.glyph, destination.label))
            else:
                item.setText(self._render_label(destination.glyph, ""))
            item.setToolTip(destination.purpose)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    @staticmethod
    def _render_label(glyph: str, label: str) -> str:
        """Compose the item text from a glyph and an optional label."""
        if not label:
            return f"  {glyph}"
        return f"  {glyph}   {label}"

    def _on_current_item_changed(
        self,
        current: QListWidgetItem | None,
        _previous: QListWidgetItem | None,
    ) -> None:
        if current is None:
            return
        identifier = current.data(Qt.ItemDataRole.UserRole)
        if isinstance(identifier, str):
            self.destination_selected.emit(identifier)