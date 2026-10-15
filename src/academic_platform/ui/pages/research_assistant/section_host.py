"""Host widget that manages a section's content region.

The host wraps a section in a scroll area with a small footer that
exposes two actions: a "Clear section" button and a summary label that
shows the section's current state. Sections that do not need the footer
or the scroll area are still hosted through this widget, because the
page's navigation contract relies on it.

Design decisions
----------------
- The host is a thin shell. It does not perform any section logic; it
  delegates to the section's lifecycle.
- The "Clear section" action is guarded by a confirmation prompt when
  the section reports that it holds state; otherwise it clears
  without prompting.
- The summary label is refreshed whenever the section is activated.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from academic_platform.ui.dialogs.confirm_dialog import ConfirmResult
from academic_platform.ui.dialogs.dialog_factory import DialogFactory
from academic_platform.ui.pages.research_assistant.section_base import (
    AssistantSection,
)

_logger = logging.getLogger(__name__)


class SectionHost(QWidget):
    """Host widget wrapping a single research assistant section."""

    #: Emitted when the section's summary changes and the page should
    #: refresh its sidebar.
    summary_changed = Signal()

    def __init__(
        self,
        section: AssistantSection,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._section = section
        self.setObjectName(f"sectionHost_{section.section_id.value}")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        scroll = QScrollArea(self)
        scroll.setObjectName("sectionScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setWidget(section)
        layout.addWidget(scroll, 1)

        footer = QFrame(self)
        footer.setObjectName("sectionFooter")
        footer.setFrameShape(QFrame.Shape.NoFrame)
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(20, 8, 20, 10)
        footer_layout.setSpacing(8)

        self._summary_label = QLabel("", footer)
        self._summary_label.setObjectName("sectionFooterSummary")
        self._summary_label.setWordWrap(True)
        footer_layout.addWidget(self._summary_label, 1)

        self._clear_button = QPushButton("Clear section", footer)
        self._clear_button.setObjectName("sectionFooterClear")
        self._clear_button.setAutoDefault(False)
        self._clear_button.clicked.connect(self._on_clear)
        footer_layout.addWidget(self._clear_button)

        layout.addWidget(footer)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    @property
    def section(self) -> AssistantSection:
        return self._section

    def refresh_summary(self) -> None:
        """Refresh the footer summary from the section's current state."""
        try:
            text = self._section.summary()
        except Exception:  # noqa: BLE001 - defensive boundary
            _logger.exception(
                "Section %s raised while computing its summary",
                self._section.section_id.value,
            )
            text = ""
        self._summary_label.setText(text or "")
        self._summary_label.setVisible(bool(text))
        self.summary_changed.emit()

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------
    def _on_clear(self) -> None:
        has_state = False
        try:
            has_state = bool(self._section.summary())
        except Exception:  # noqa: BLE001 - defensive boundary
            has_state = False
        if has_state:
            outcome = DialogFactory.confirm(
                self,
                "Clear section",
                (
                    f"Clear the work in {self._section.title!r}? "
                    "This action cannot be undone."
                ),
                confirm_label="Clear",
                cancel_label="Cancel",
                destructive=True,
                default_to_confirm=False,
            )
            if outcome.result is not ConfirmResult.CONFIRMED:
                return
        try:
            self._section.reset()
        except Exception:  # noqa: BLE001 - defensive boundary
            _logger.exception(
                "Section %s raised while resetting",
                self._section.section_id.value,
            )
        self.refresh_summary()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def on_activated(self) -> None:
        try:
            self._section.on_activated()
        except Exception:  # noqa: BLE001 - defensive boundary
            _logger.exception(
                "Section %s raised in on_activated",
                self._section.section_id.value,
            )
        self.refresh_summary()

    def on_deactivated(self) -> None:
        try:
            self._section.on_deactivated()
        except Exception:  # noqa: BLE001 - defensive boundary
            _logger.exception(
                "Section %s raised in on_deactivated",
                self._section.section_id.value,
            )