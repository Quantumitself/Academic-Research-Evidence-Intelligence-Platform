"""Modal dialog for the reader → assistant handoff.

The dialog previews the handoff payload and lets the user choose which
fields to include. On accept, the dialog rebuilds the payload with the
chosen options and stores it. The assistant destination consumes the
stored payload when the user navigates there.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from academic_platform.application.assistant_handoff.errors import (
    AssistantHandoffError,
    AssistantHandoffNotFoundError,
)
from academic_platform.application.assistant_handoff.model import (
    AssistantHandoff,
    HandoffOptions,
)
from academic_platform.application.assistant_handoff.service import (
    AssistantHandoffService,
)

_logger = logging.getLogger(__name__)


class AssistantHandoffDialog(QDialog):
    """Modal dialog presenting a handoff preview."""

    handoff_prepared = Signal(object)  # AssistantHandoff

    def __init__(
        self,
        service: AssistantHandoffService,
        document_key: str,
        *,
        current_page: int | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._service = service
        self._document_key = document_key
        self._current_page = current_page
        self._handoff: AssistantHandoff | None = None

        self.setObjectName("assistantHandoffDialog")
        self.setWindowTitle("Hand off to research assistant")
        self.setModal(True)
        self.setMinimumSize(600, 520)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)

        heading = QLabel(
            "The research assistant will use the following context when "
            "you navigate to it. Choose which details to include.",
            self,
        )
        heading.setObjectName("handoffDialogHeading")
        heading.setWordWrap(True)
        layout.addWidget(heading)

        options_row = QHBoxLayout()
        options_row.setContentsMargins(0, 0, 0, 0)
        options_row.setSpacing(8)

        self._metadata_checkbox = QCheckBox("Metadata", self)
        self._metadata_checkbox.setObjectName("handoffIncludeMetadata")
        self._metadata_checkbox.setChecked(True)
        self._metadata_checkbox.toggled.connect(self._rebuild)
        options_row.addWidget(self._metadata_checkbox)

        self._excerpt_checkbox = QCheckBox("Current page excerpt", self)
        self._excerpt_checkbox.setObjectName("handoffIncludeExcerpt")
        self._excerpt_checkbox.setChecked(True)
        self._excerpt_checkbox.toggled.connect(self._rebuild)
        options_row.addWidget(self._excerpt_checkbox)

        self._annotations_checkbox = QCheckBox("Annotations", self)
        self._annotations_checkbox.setObjectName("handoffIncludeAnnotations")
        self._annotations_checkbox.setChecked(False)
        self._annotations_checkbox.toggled.connect(self._rebuild)
        options_row.addWidget(self._annotations_checkbox)

        options_row.addStretch(1)
        layout.addLayout(options_row)

        self._summary_label = QLabel("", self)
        self._summary_label.setObjectName("handoffDialogSummary")
        self._summary_label.setWordWrap(True)
        layout.addWidget(self._summary_label)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self._preview = QPlainTextEdit(scroll)
        self._preview.setObjectName("handoffDialogPreview")
        self._preview.setReadOnly(True)
        scroll.setWidget(self._preview)
        layout.addWidget(scroll, 1)

        button_box = QDialogButtonBox(self)
        button_box.setObjectName("handoffDialogButtonBox")
        self._send_button = button_box.addButton(
            "Prepare handoff", QDialogButtonBox.ButtonRole.AcceptRole
        )
        self._cancel_button = button_box.addButton(
            "Cancel", QDialogButtonBox.ButtonRole.RejectRole
        )
        self._send_button.setObjectName("handoffDialogSend")
        self._cancel_button.setObjectName("handoffDialogCancel")
        button_box.accepted.connect(self._on_accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        self._rebuild()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def handoff(self) -> AssistantHandoff | None:
        return self._handoff

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------
    def _rebuild(self) -> None:
        options = self._current_options()
        try:
            handoff = self._service.build_handoff(
                self._document_key,
                current_page=self._current_page,
                options=options,
            )
        except (AssistantHandoffNotFoundError, AssistantHandoffError) as exc:
            _logger.warning("Unable to prepare handoff: %s", exc)
            self._handoff = None
            self._send_button.setEnabled(False)
            self._summary_label.setText(str(exc))
            self._preview.setPlainText("")
            return
        self._handoff = handoff
        self._send_button.setEnabled(True)
        self._summary_label.setText(handoff.summary)
        self._preview.setPlainText(_render_preview(handoff))

    def _on_accept(self) -> None:
        if self._handoff is None:
            self.reject()
            return
        self.handoff_prepared.emit(self._handoff)
        self.accept()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _current_options(self) -> HandoffOptions:
        return HandoffOptions(
            include_metadata=self._metadata_checkbox.isChecked(),
            include_current_page_text=self._excerpt_checkbox.isChecked(),
            include_annotations=self._annotations_checkbox.isChecked(),
        )


# ----------------------------------------------------------------------
# Rendering helpers
# ----------------------------------------------------------------------
def _render_preview(handoff: AssistantHandoff) -> str:
    lines: list[str] = []
    lines.append(f"Title: {handoff.title or '(untitled)'}")
    if handoff.authors:
        lines.append(f"Authors: {', '.join(handoff.authors)}")
    if handoff.year is not None:
        lines.append(f"Year: {handoff.year}")
    if handoff.venue:
        lines.append(f"Venue: {handoff.venue}")
    if handoff.doi:
        lines.append(f"DOI: {handoff.doi}")
    if handoff.current_page is not None:
        total = handoff.page_count if handoff.page_count is not None else "?"
        lines.append(f"Current page: {handoff.current_page} of {total}")
    if handoff.abstract:
        lines.append("")
        lines.append("Abstract:")
        lines.append(handoff.abstract)
    if handoff.page_text_excerpt:
        lines.append("")
        lines.append("Current page excerpt:")
        lines.append(handoff.page_text_excerpt)
    if handoff.annotations:
        lines.append("")
        lines.append("Annotations:")
        for annotation in handoff.annotations:
            lines.append(f"- {annotation}")
    return "\n".join(lines)