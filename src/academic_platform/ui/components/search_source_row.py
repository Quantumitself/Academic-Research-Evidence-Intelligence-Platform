"""Search source configuration row.

Displays a search source's name, type, enabled state, and last-error
summary. Emits typed signals for testing, editing, toggling enabled state,
and removal.

Design decisions
----------------
- The row carries only a summary payload. The full source configuration is
  owned by the search source registry in a later phase.
- The enable checkbox mirrors the pattern used by ``AIProviderCard``: the
  caller owns the state and reflects it back with ``set_enabled``.
- The last-error summary is truncated to a single line. Full diagnostics
  belong in the logs; the row is a summary view.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from academic_platform.ui.components.stat_badge import StatBadge, StatBadgeTone


class SourceType(str, Enum):
    """The kind of search source."""

    BUILT_IN = "built_in"
    USER_DEFINED = "user_defined"


@dataclass(frozen=True, slots=True)
class SearchSourceSummary:
    """Presentation payload for a search source row."""

    identifier: str
    name: str
    source_type: SourceType
    enabled: bool = True
    last_test_ok: bool | None = None
    last_error: str = ""
    supports_filters: tuple[str, ...] = ()


class SearchSourceRow(QFrame):
    """Search source configuration row."""

    test_requested = Signal(str)
    edit_requested = Signal(str)
    remove_requested = Signal(str)
    enabled_toggled = Signal(str, bool)

    def __init__(
        self,
        source: SearchSourceSummary,
        *,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("searchSourceRow")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self._source = source

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(6)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(8)

        self._enabled_checkbox = QCheckBox(self)
        self._enabled_checkbox.setObjectName("searchSourceRowEnabled")
        self._enabled_checkbox.setChecked(source.enabled)
        self._enabled_checkbox.setToolTip(
            "Enable or disable this source. Disabled sources are never queried."
        )
        self._enabled_checkbox.toggled.connect(
            lambda checked: self.enabled_toggled.emit(source.identifier, checked)
        )
        header.addWidget(self._enabled_checkbox)

        name = QLabel(source.name, self)
        name.setObjectName("searchSourceRowName")
        name.setWordWrap(True)
        header.addWidget(name, 1)

        header.addWidget(
            StatBadge(
                "Type",
                "Built-in" if source.source_type is SourceType.BUILT_IN else "Custom",
                parent=self,
            ),
            0,
            Qt.AlignmentFlag.AlignTop,
        )

        if source.last_test_ok is True:
            header.addWidget(
                StatBadge("Test", "OK", tone=StatBadgeTone.POSITIVE, parent=self),
                0,
                Qt.AlignmentFlag.AlignTop,
            )
        elif source.last_test_ok is False:
            header.addWidget(
                StatBadge("Test", "Failed", tone=StatBadgeTone.DANGER, parent=self),
                0,
                Qt.AlignmentFlag.AlignTop,
            )
        layout.addLayout(header)

        if source.supports_filters:
            filters_line = QLabel(
                "Supported filters: " + ", ".join(source.supports_filters),
                self,
            )
            filters_line.setObjectName("searchSourceRowFilters")
            filters_line.setWordWrap(True)
            layout.addWidget(filters_line)

        if source.last_error:
            error_label = QLabel(source.last_error, self)
            error_label.setObjectName("searchSourceRowError")
            error_label.setWordWrap(True)
            error_label.setMaximumHeight(40)
            layout.addWidget(error_label)

        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(6)

        self._test_button = QPushButton("Test", self)
        self._test_button.setObjectName("searchSourceRowTest")
        self._test_button.setEnabled(False)
        self._test_button.clicked.connect(
            lambda: self.test_requested.emit(source.identifier)
        )
        actions.addWidget(self._test_button)

        self._edit_button = QPushButton("Edit", self)
        self._edit_button.setObjectName("searchSourceRowEdit")
        self._edit_button.setEnabled(False)
        self._edit_button.clicked.connect(
            lambda: self.edit_requested.emit(source.identifier)
        )
        actions.addWidget(self._edit_button)

        self._remove_button = QPushButton("Remove", self)
        self._remove_button.setObjectName("searchSourceRowRemove")
        self._remove_button.setEnabled(False)
        self._remove_button.clicked.connect(
            lambda: self.remove_requested.emit(source.identifier)
        )
        actions.addWidget(self._remove_button)

        actions.addStretch(1)
        layout.addLayout(actions)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def enable_test(self, enabled: bool = True) -> None:
        self._test_button.setEnabled(enabled)

    def enable_edit(self, enabled: bool = True) -> None:
        self._edit_button.setEnabled(enabled)

    def enable_remove(self, enabled: bool = True) -> None:
        self._remove_button.setEnabled(enabled)

    def set_enabled(self, enabled: bool) -> None:
        """Reflect the persisted enabled state without re-emitting the signal."""
        self._enabled_checkbox.blockSignals(True)
        self._enabled_checkbox.setChecked(enabled)
        self._enabled_checkbox.blockSignals(False)

    @property
    def identifier(self) -> str:
        return self._source.identifier

    @property
    def source(self) -> SearchSourceSummary:
        return self._source