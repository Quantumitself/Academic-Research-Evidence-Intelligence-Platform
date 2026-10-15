"""Modal dialog for project export.

The dialog lets the user pick the output format, the destination file,
and which sections to include. It delegates the actual export to the
application-layer ``ProjectExportService``.
"""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from academic_platform.application.project_export.errors import (
    ProjectExportError,
    ProjectExportNotFoundError,
)
from academic_platform.application.project_export.model import (
    ExportFormat,
    ExportOptions,
    ExportResult,
    ExportSection,
)
from academic_platform.application.project_export.service import (
    ProjectExportService,
)
from academic_platform.ui.dialogs.dialog_factory import DialogFactory
from academic_platform.ui.dialogs.message_dialog import MessageKind

_logger = logging.getLogger(__name__)


class ProjectExportDialog(QDialog):
    """Modal dialog driving the project export."""

    exported = Signal(object)  # ExportResult

    def __init__(
        self,
        service: ProjectExportService,
        project_key: str,
        *,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._service = service
        self._project_key = project_key
        self._result: ExportResult | None = None

        self.setObjectName("projectExportDialog")
        self.setWindowTitle("Export project")
        self.setModal(True)
        self.setMinimumSize(540, 480)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(10)

        heading = QLabel(
            "Export the project and its related entities to a "
            "self-contained file.",
            self,
        )
        heading.setObjectName("projectExportHeading")
        heading.setWordWrap(True)
        layout.addWidget(heading)

        format_row = QHBoxLayout()
        format_row.setContentsMargins(0, 0, 0, 0)
        format_row.setSpacing(8)

        format_label = QLabel("Format:", self)
        format_label.setObjectName("projectExportFormatLabel")
        format_row.addWidget(format_label)

        self._format_combo = QComboBox(self)
        self._format_combo.setObjectName("projectExportFormat")
        for export_format in ExportFormat:
            self._format_combo.addItem(
                export_format.display_name, export_format.value
            )
        self._format_combo.currentIndexChanged.connect(self._on_format_changed)
        format_row.addWidget(self._format_combo)
        format_row.addStretch(1)
        layout.addLayout(format_row)

        path_row = QHBoxLayout()
        path_row.setContentsMargins(0, 0, 0, 0)
        path_row.setSpacing(8)

        self._path_input = QLineEdit(self)
        self._path_input.setObjectName("projectExportPath")
        path_row.addWidget(self._path_input, 1)

        self._browse_button = QPushButton("Browse…", self)
        self._browse_button.setObjectName("projectExportBrowse")
        self._browse_button.setAutoDefault(False)
        self._browse_button.clicked.connect(self._on_browse)
        path_row.addWidget(self._browse_button)
        layout.addLayout(path_row)

        sections_label = QLabel("Sections to include:", self)
        sections_label.setObjectName("projectExportSectionsLabel")
        layout.addWidget(sections_label)

        self._section_checkboxes: dict[ExportSection, QCheckBox] = {}
        for section in ExportSection:
            checkbox = QCheckBox(section.display_name, self)
            checkbox.setObjectName(f"projectExportSection_{section.value}")
            checkbox.setChecked(True)
            self._section_checkboxes[section] = checkbox
            layout.addWidget(checkbox)

        self._overwrite_checkbox = QCheckBox(
            "Overwrite the destination if it exists", self
        )
        self._overwrite_checkbox.setObjectName("projectExportOverwrite")
        layout.addWidget(self._overwrite_checkbox)

        layout.addStretch(1)

        button_box = QDialogButtonBox(self)
        button_box.setObjectName("projectExportButtonBox")
        self._export_button = button_box.addButton(
            "Export", QDialogButtonBox.ButtonRole.AcceptRole
        )
        self._cancel_button = button_box.addButton(
            "Cancel", QDialogButtonBox.ButtonRole.RejectRole
        )
        self._export_button.setObjectName("projectExportAccept")
        self._cancel_button.setObjectName("projectExportCancel")
        button_box.accepted.connect(self._on_accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        self._set_default_path()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def result_value(self) -> ExportResult | None:
        return self._result

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------
    def _on_format_changed(self, _index: int) -> None:
        self._set_default_path()

    def _on_browse(self) -> None:
        current = self._path_input.text().strip()
        filters = (
            "JSON files (*.json);;All files (*)"
            if self._current_format() is ExportFormat.JSON
            else "Markdown files (*.md);;All files (*)"
        )
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export project",
            current,
            filters,
        )
        if path:
            self._path_input.setText(path)

    def _on_accept(self) -> None:
        path_text = self._path_input.text().strip()
        if not path_text:
            _logger.warning("Export requested without a destination")
            return
        options = ExportOptions(
            format=self._current_format(),
            sections=frozenset(
                section
                for section, checkbox in self._section_checkboxes.items()
                if checkbox.isChecked()
            ),
        )
        try:
            result = self._service.export(
                self._project_key,
                Path(path_text),
                options=options,
                overwrite=self._overwrite_checkbox.isChecked(),
            )
        except ProjectExportNotFoundError as exc:
            self._show_error("Project not found", str(exc))
            return
        except ProjectExportError as exc:
            self._show_error("Export failed", str(exc))
            return
        self._result = result
        self.exported.emit(result)
        self.accept()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _current_format(self) -> ExportFormat:
        data = self._format_combo.currentData()
        try:
            return ExportFormat(data)
        except (TypeError, ValueError):
            return ExportFormat.JSON

    def _set_default_path(self) -> None:
        export_format = self._current_format()
        try:
            suggested = self._service.suggested_filename(
                self._project_key, export_format
            )
        except ProjectExportError:
            suggested = f"project{export_format.extension}"
        # Anchor the suggested path under the user's home directory.
        default_path = Path.home() / suggested
        current = self._path_input.text().strip()
        if not current:
            self._path_input.setText(str(default_path))
            return
        existing = Path(current)
        # If the current path has an extension matching the other format,
        # swap it; otherwise leave it unchanged.
        if existing.suffix.lower() in {".json", ".md"}:
            self._path_input.setText(
                str(existing.with_suffix(export_format.extension))
            )

    def _show_error(self, title: str, message: str) -> None:
        DialogFactory.message(self, title, message, kind=MessageKind.ERROR)