"""Collection summary card.

Displays the title, description, item count, and the first few item titles
of a collection. Emits typed signals for opening, editing, and exporting.

Design decisions
----------------
- The card accepts a plain payload rather than a domain object.
- The preview list is capped at a fixed number of items so that the card
  maintains a stable height. The cap is a presentation constant.
- The card does not fetch the item list; the caller supplies a preview.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from academic_platform.ui.components.stat_badge import StatBadge


_PREVIEW_LIMIT = 3


@dataclass(frozen=True, slots=True)
class CollectionSummary:
    """Presentation payload for a collection card."""

    identifier: str
    title: str
    description: str = ""
    item_count: int = 0
    preview_items: tuple[str, ...] = field(default_factory=tuple)
    updated_at: str = ""


class CollectionCard(QFrame):
    """Collection summary card."""

    opened = Signal(str)
    edited = Signal(str)
    exported = Signal(str)

    def __init__(
        self,
        collection: CollectionSummary,
        *,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("collectionCard")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self._collection = collection

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)

        title = QLabel(collection.title or "(untitled collection)", self)
        title.setObjectName("collectionCardTitle")
        title.setWordWrap(True)
        layout.addWidget(title)

        if collection.description:
            description = QLabel(collection.description, self)
            description.setObjectName("collectionCardDescription")
            description.setWordWrap(True)
            layout.addWidget(description)

        meta_row = QHBoxLayout()
        meta_row.setContentsMargins(0, 0, 0, 0)
        meta_row.setSpacing(6)
        meta_row.addWidget(StatBadge("Items", str(collection.item_count), parent=self))
        if collection.updated_at:
            meta_row.addWidget(StatBadge("Updated", collection.updated_at, parent=self))
        meta_row.addStretch(1)
        layout.addLayout(meta_row)

        if collection.preview_items:
            preview_lines = list(collection.preview_items[:_PREVIEW_LIMIT])
            remaining = len(collection.preview_items) - _PREVIEW_LIMIT
            if remaining > 0:
                preview_lines.append(f"… and {remaining} more")
            preview_text = "\n".join(f"• {line}" for line in preview_lines)
            preview = QLabel(preview_text, self)
            preview.setObjectName("collectionCardPreview")
            preview.setWordWrap(True)
            layout.addWidget(preview)

        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(6)

        self._open_button = QPushButton("Open", self)
        self._open_button.setObjectName("collectionCardOpen")
        self._open_button.setEnabled(False)
        self._open_button.clicked.connect(
            lambda: self.opened.emit(collection.identifier)
        )
        actions.addWidget(self._open_button)

        self._edit_button = QPushButton("Edit", self)
        self._edit_button.setObjectName("collectionCardEdit")
        self._edit_button.setEnabled(False)
        self._edit_button.clicked.connect(
            lambda: self.edited.emit(collection.identifier)
        )
        actions.addWidget(self._edit_button)

        self._export_button = QPushButton("Export", self)
        self._export_button.setObjectName("collectionCardExport")
        self._export_button.setEnabled(False)
        self._export_button.clicked.connect(
            lambda: self.exported.emit(collection.identifier)
        )
        actions.addWidget(self._export_button)

        actions.addStretch(1)
        layout.addLayout(actions)

        self.setCursor(Qt.CursorShape.PointingHandCursor)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def enable_open(self, enabled: bool = True) -> None:
        self._open_button.setEnabled(enabled)

    def enable_edit(self, enabled: bool = True) -> None:
        self._edit_button.setEnabled(enabled)

    def enable_export(self, enabled: bool = True) -> None:
        self._export_button.setEnabled(enabled)

    @property
    def identifier(self) -> str:
        return self._collection.identifier

    @property
    def collection(self) -> CollectionSummary:
        return self._collection

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802 - Qt API
        self.opened.emit(self._collection.identifier)
        super().mouseDoubleClickEvent(event)