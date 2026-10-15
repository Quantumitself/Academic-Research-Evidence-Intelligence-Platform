"""Annotation side panel for the reader.

The panel lists the current document's annotations, offers actions to
create a note, highlight, or bookmark on the current page, provides an
editor for updating a selected annotation, and supports deletion and
export.

Design decisions
----------------
- The panel is a self-contained widget. It reads and writes through the
  application-layer ``AnnotationService``.
- The panel is told which document and page are current by the reader
  page. It never inspects the reader's internal state.
- The panel emits ``annotation_selected`` when the user activates an
  annotation so that the reader can jump to the annotation's page.
- Destructive actions are guarded by a confirmation prompt from the
  dialog factory.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from academic_platform.application.annotations.errors import (
    AnnotationError,
    AnnotationNotFoundError,
)
from academic_platform.application.annotations.model import (
    AnnotationColor,
    AnnotationKind,
    AnnotationView,
)
from academic_platform.application.annotations.service import (
    AnnotationService,
)
from academic_platform.ui.dialogs.confirm_dialog import ConfirmResult
from academic_platform.ui.dialogs.dialog_factory import DialogFactory
from academic_platform.ui.dialogs.message_dialog import MessageKind
from academic_platform.ui.notifications.service import NotificationService

_logger = logging.getLogger(__name__)


class AnnotationPanel(QFrame):
    """Side panel exposing the annotation workflow."""

    annotation_selected = Signal(int, int)  # annotation_id, page_number

    def __init__(
        self,
        *,
        notification_service: NotificationService | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("annotationPanel")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self._service: AnnotationService | None = None
        self._notification_service = notification_service
        self._document_key: str = ""
        self._current_page: int = 1
        self._current_annotation_id: int | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 12)
        layout.setSpacing(6)

        heading = QLabel("Annotations", self)
        heading.setObjectName("annotationPanelHeading")
        layout.addWidget(heading)

        self._summary_label = QLabel("No document is open.", self)
        self._summary_label.setObjectName("annotationPanelSummary")
        self._summary_label.setWordWrap(True)
        layout.addWidget(self._summary_label)

        actions_row = QHBoxLayout()
        actions_row.setContentsMargins(0, 0, 0, 0)
        actions_row.setSpacing(4)

        self._add_note_button = QPushButton("Note", self)
        self._add_note_button.setObjectName("annotationAddNote")
        self._add_note_button.setAutoDefault(False)
        self._add_note_button.clicked.connect(self._on_add_note)
        actions_row.addWidget(self._add_note_button)

        self._add_highlight_button = QPushButton("Highlight", self)
        self._add_highlight_button.setObjectName("annotationAddHighlight")
        self._add_highlight_button.setAutoDefault(False)
        self._add_highlight_button.clicked.connect(self._on_add_highlight)
        actions_row.addWidget(self._add_highlight_button)

        self._add_bookmark_button = QPushButton("Bookmark", self)
        self._add_bookmark_button.setObjectName("annotationAddBookmark")
        self._add_bookmark_button.setAutoDefault(False)
        self._add_bookmark_button.clicked.connect(self._on_add_bookmark)
        actions_row.addWidget(self._add_bookmark_button)

        layout.addLayout(actions_row)

        self._color_combo = QComboBox(self)
        self._color_combo.setObjectName("annotationColorCombo")
        for color in AnnotationColor:
            self._color_combo.addItem(color.value.capitalize(), color.value)
        layout.addWidget(self._color_combo)

        self._list = QListWidget(self)
        self._list.setObjectName("annotationList")
        self._list.setAlternatingRowColors(False)
        self._list.currentItemChanged.connect(self._on_annotation_selected)
        self._list.itemDoubleClicked.connect(self._on_annotation_activated)
        layout.addWidget(self._list, 1)

        editor_label = QLabel("Editor", self)
        editor_label.setObjectName("annotationEditorLabel")
        layout.addWidget(editor_label)

        self._editor = QPlainTextEdit(self)
        self._editor.setObjectName("annotationEditor")
        self._editor.setPlaceholderText("Write a note here…")
        layout.addWidget(self._editor, 1)

        editor_actions = QHBoxLayout()
        editor_actions.setContentsMargins(0, 0, 0, 0)
        editor_actions.setSpacing(4)

        self._save_button = QPushButton("Save", self)
        self._save_button.setObjectName("annotationSave")
        self._save_button.setAutoDefault(False)
        self._save_button.setEnabled(False)
        self._save_button.clicked.connect(self._on_save)
        editor_actions.addWidget(self._save_button)

        self._delete_button = QPushButton("Delete", self)
        self._delete_button.setObjectName("annotationDelete")
        self._delete_button.setAutoDefault(False)
        self._delete_button.setEnabled(False)
        self._delete_button.clicked.connect(self._on_delete)
        editor_actions.addWidget(self._delete_button)

        editor_actions.addStretch(1)
        layout.addLayout(editor_actions)

        export_row = QHBoxLayout()
        export_row.setContentsMargins(0, 0, 0, 0)
        export_row.setSpacing(4)

        self._export_json_button = QPushButton("Export JSON…", self)
        self._export_json_button.setObjectName("annotationExportJson")
        self._export_json_button.setAutoDefault(False)
        self._export_json_button.clicked.connect(self._on_export_json)
        export_row.addWidget(self._export_json_button)

        self._export_markdown_button = QPushButton("Export Markdown…", self)
        self._export_markdown_button.setObjectName("annotationExportMarkdown")
        self._export_markdown_button.setAutoDefault(False)
        self._export_markdown_button.clicked.connect(self._on_export_markdown)
        export_row.addWidget(self._export_markdown_button)

        layout.addLayout(export_row)
        # The add and export actions require an open document. They are
        # enabled once ``set_document`` receives a non-empty key.
        self._set_action_state(False)
        
    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def attach_service(self, service: AnnotationService) -> None:
        self._service = service
        self.refresh()

    def set_document(self, document_key: str, page_number: int) -> None:
        self._document_key = document_key
        self._current_page = page_number
        self.refresh()

    def set_current_page(self, page_number: int) -> None:
        self._current_page = page_number

    def refresh(self) -> None:
        self._clear_list()
        if self._service is None:
            self._summary_label.setText("Annotation service is not attached.")
            self._set_action_state(False)
            return
        if not self._document_key:
            self._summary_label.setText("No document is open.")
            self._set_action_state(False)
            return
        try:
            views = self._service.list_for_document(self._document_key)
        except AnnotationError as exc:
            _logger.warning("Unable to list annotations: %s", exc)
            self._summary_label.setText("Unable to read annotations.")
            self._set_action_state(False)
            return
        self._summary_label.setText(
            f"{len(views)} annotation(s) on {self._document_key}."
        )
        self._set_action_state(True)
        for view in views:
            item = QListWidgetItem(view.display_label)
            item.setData(Qt.ItemDataRole.UserRole, view.identifier)
            item.setData(Qt.ItemDataRole.UserRole + 1, view.page_number or 0)
            self._list.addItem(item)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------
    def _on_add_note(self) -> None:
        if self._service is None or not self._document_key:
            return
        body = DialogFactory.prompt(
            self,
            "Add note",
            "Note",
            initial="",
            placeholder="Write a note about this page…",
        )
        if body is None or not body.strip():
            return
        try:
            self._service.create_note(
                self._document_key, self._current_page, body.strip()
            )
        except AnnotationError as exc:
            self._show_error("Unable to add note", str(exc))
            return
        self._notify("Note added", f"Page {self._current_page}")
        self.refresh()

    def _on_add_highlight(self) -> None:
        if self._service is None or not self._document_key:
            return
        excerpt = DialogFactory.prompt(
            self,
            "Add highlight",
            "Highlighted text",
            initial="",
            placeholder="Paste or type the excerpt…",
        )
        if excerpt is None or not excerpt.strip():
            return
        color_data = self._color_combo.currentData()
        try:
            color = AnnotationColor(color_data) if color_data else AnnotationColor.YELLOW
        except ValueError:
            color = AnnotationColor.YELLOW
        try:
            self._service.create_highlight(
                self._document_key,
                self._current_page,
                excerpt.strip(),
                color=color,
            )
        except AnnotationError as exc:
            self._show_error("Unable to add highlight", str(exc))
            return
        self._notify("Highlight added", f"Page {self._current_page}")
        self.refresh()

    def _on_add_bookmark(self) -> None:
        if self._service is None or not self._document_key:
            return
        try:
            self._service.create_bookmark(self._document_key, self._current_page)
        except AnnotationError as exc:
            self._show_error("Unable to add bookmark", str(exc))
            return
        self._notify("Bookmark added", f"Page {self._current_page}")
        self.refresh()

    def _on_annotation_selected(
        self,
        current: QListWidgetItem | None,
        _previous: QListWidgetItem | None,
    ) -> None:
        if current is None:
            self._current_annotation_id = None
            self._editor.setPlainText("")
            self._save_button.setEnabled(False)
            self._delete_button.setEnabled(False)
            return
        annotation_id = current.data(Qt.ItemDataRole.UserRole)
        try:
            annotation_id = int(annotation_id)
        except (TypeError, ValueError):
            return
        self._current_annotation_id = annotation_id
        self._save_button.setEnabled(True)
        self._delete_button.setEnabled(True)
        if self._service is None:
            return
        try:
            view = self._service.get(annotation_id)
        except AnnotationNotFoundError:
            self._editor.setPlainText("")
            return
        except AnnotationError as exc:
            _logger.warning("Unable to load annotation: %s", exc)
            return
        self._editor.setPlainText(view.body or "")
        if view.color is not None:
            for index in range(self._color_combo.count()):
                if self._color_combo.itemData(index) == view.color.value:
                    self._color_combo.setCurrentIndex(index)
                    break

    def _on_annotation_activated(self, item: QListWidgetItem) -> None:
        page = item.data(Qt.ItemDataRole.UserRole + 1)
        annotation_id = item.data(Qt.ItemDataRole.UserRole)
        try:
            page_number = int(page)
            annotation_id_int = int(annotation_id)
        except (TypeError, ValueError):
            return
        if page_number > 0:
            self.annotation_selected.emit(annotation_id_int, page_number)

    def _on_save(self) -> None:
        if self._service is None or self._current_annotation_id is None:
            return
        body = self._editor.toPlainText()
        color_data = self._color_combo.currentData()
        try:
            color = AnnotationColor(color_data) if color_data else None
        except ValueError:
            color = None
        try:
            self._service.update(
                self._current_annotation_id,
                body=body,
                color=color,
            )
        except AnnotationNotFoundError:
            self._show_error(
                "Annotation not found",
                "The annotation has been removed. Refresh the panel.",
            )
            self.refresh()
            return
        except AnnotationError as exc:
            self._show_error("Unable to save annotation", str(exc))
            return
        self._notify("Annotation saved", "")
        self.refresh()

    def _on_delete(self) -> None:
        if self._service is None or self._current_annotation_id is None:
            return
        outcome = DialogFactory.confirm(
            self,
            "Delete annotation",
            "Delete this annotation? This action cannot be undone.",
            confirm_label="Delete",
            cancel_label="Cancel",
            destructive=True,
            default_to_confirm=False,
        )
        if outcome.result is not ConfirmResult.CONFIRMED:
            return
        try:
            self._service.delete(self._current_annotation_id)
        except AnnotationError as exc:
            self._show_error("Unable to delete annotation", str(exc))
            return
        self._current_annotation_id = None
        self._editor.setPlainText("")
        self._save_button.setEnabled(False)
        self._delete_button.setEnabled(False)
        self._notify("Annotation deleted", "")
        self.refresh()

    def _on_export_json(self) -> None:
        if self._service is None or not self._document_key:
            return
        try:
            payload = self._service.export_to_json(self._document_key)
        except AnnotationError as exc:
            self._show_error("Unable to export annotations", str(exc))
            return
        path = _save_export(self, "annotations.json")
        if path is None:
            return
        try:
            path.write_text(payload, encoding="utf-8")
        except OSError as exc:
            self._show_error("Unable to write the export", str(exc))
            return
        self._notify("Annotations exported", str(path))

    def _on_export_markdown(self) -> None:
        if self._service is None or not self._document_key:
            return
        try:
            payload = self._service.export_to_markdown(self._document_key)
        except AnnotationError as exc:
            self._show_error("Unable to export annotations", str(exc))
            return
        path = _save_export(self, "annotations.md")
        if path is None:
            return
        try:
            path.write_text(payload, encoding="utf-8")
        except OSError as exc:
            self._show_error("Unable to write the export", str(exc))
            return
        self._notify("Annotations exported", str(path))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _clear_list(self) -> None:
        self._list.clear()
        self._current_annotation_id = None
        self._editor.setPlainText("")
        self._save_button.setEnabled(False)
        self._delete_button.setEnabled(False)

    def _set_action_state(self, enabled: bool) -> None:
        self._add_note_button.setEnabled(enabled)
        self._add_highlight_button.setEnabled(enabled)
        self._add_bookmark_button.setEnabled(enabled)
        self._export_json_button.setEnabled(enabled)
        self._export_markdown_button.setEnabled(enabled)

    def _show_error(self, title: str, message: str) -> None:
        DialogFactory.message(self, title, message, kind=MessageKind.ERROR)

    def _notify(self, title: str, message: str) -> None:
        if self._notification_service is None:
            return
        self._notification_service.success(title, message)


def _save_export(parent: QWidget, suggested_name: str):
    from PySide6.QtWidgets import QFileDialog

    path, _ = QFileDialog.getSaveFileName(
        parent,
        "Export annotations",
        suggested_name,
    )
    if not path:
        return None
    from pathlib import Path

    return Path(path)