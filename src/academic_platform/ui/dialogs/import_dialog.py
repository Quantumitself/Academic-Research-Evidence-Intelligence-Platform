"""Multi-file import dialog.

The dialog presents a plan produced by the application-layer
``ImportCoordinator``. It renders each candidate with its validation
state, allows the user to select which candidates to import, exposes the
import-mode selector, offers a "re-import duplicates" toggle, and
returns the confirmed selection to the caller.

Design decisions
----------------
- The dialog is a thin presentation layer over the coordinator. It
  never performs validation, checksum computation, or filesystem
  operations itself.
- File selection uses the platform file dialog. The selected paths are
  passed to the coordinator's ``prepare`` method, which returns the
  plan.
- The list of candidates is rendered with a custom row widget so that
  the state, size, and duplicate information are visible at a glance.
- Import execution runs synchronously inside the dialog because the
  coordinator's work is bounded by the number of files the user
  selected and by the size of each file. The dialog displays a busy
  cursor while the import runs.
- The dialog does not commit. The coordinator runs inside a unit of work
  supplied by the caller through the coordinator factory.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from academic_platform.application.library_import.coordinator import (
    ImportCoordinator,
)
from academic_platform.application.library_import.errors import (
    ImportError,
)
from academic_platform.application.library_import.model import (
    ImportCandidate,
    ImportCandidateState,
    ImportMode,
    ImportPlan,
    ImportResult,
)
from academic_platform.ui.dialogs.dialog_factory import DialogFactory
from academic_platform.ui.dialogs.message_dialog import MessageKind
from academic_platform.ui.notifications.service import NotificationService

_logger = logging.getLogger(__name__)


class ImportDialog(QDialog):
    """Modal dialog driving the library import workflow."""

    imported = Signal(object)  # ImportResult

    def __init__(
        self,
        coordinator_factory: Callable[[], ImportCoordinator],
        paths: list[Path],
        *,
        default_mode: ImportMode = ImportMode.MANAGED_COPY,
        notification_service: NotificationService | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._coordinator_factory = coordinator_factory
        self._paths = list(paths)
        self._notification_service = notification_service
        self._plan: ImportPlan | None = None
        self._checkboxes: dict[Path, QCheckBox] = {}

        self.setObjectName("importDialog")
        self.setWindowTitle("Import files")
        self.setModal(True)
        self.setMinimumSize(720, 560)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)

        header = QLabel(
            "Review the files below. Unsupported or oversized files are "
            "marked and will be skipped. Duplicate files are marked and "
            "may be re-imported if you choose.",
            self,
        )
        header.setObjectName("importDialogHeader")
        header.setWordWrap(True)
        layout.addWidget(header)

        controls = QHBoxLayout()
        controls.setContentsMargins(0, 0, 0, 0)
        controls.setSpacing(8)

        mode_label = QLabel("Storage mode:", self)
        mode_label.setObjectName("importDialogModeLabel")
        controls.addWidget(mode_label)

        self._mode_combo = QComboBox(self)
        self._mode_combo.setObjectName("importDialogMode")
        self._mode_combo.addItem("Copy into library", ImportMode.MANAGED_COPY.value)
        self._mode_combo.addItem("Reference original file", ImportMode.REFERENCED_FILE.value)
        for index in range(self._mode_combo.count()):
            if self._mode_combo.itemData(index) == default_mode.value:
                self._mode_combo.setCurrentIndex(index)
                break
        self._mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        controls.addWidget(self._mode_combo)

        self._import_duplicates_checkbox = QCheckBox("Re-import duplicates", self)
        self._import_duplicates_checkbox.setObjectName("importDialogDuplicates")
        self._import_duplicates_checkbox.setToolTip(
            "When enabled, files that already exist in the library are "
            "imported again as new records. When disabled, they are "
            "skipped."
        )
        controls.addWidget(self._import_duplicates_checkbox)

        self._select_all_button = QPushButton("Select all", self)
        self._select_all_button.setObjectName("importDialogSelectAll")
        self._select_all_button.setAutoDefault(False)
        self._select_all_button.clicked.connect(self._on_select_all)
        controls.addWidget(self._select_all_button)

        self._clear_selection_button = QPushButton("Clear", self)
        self._clear_selection_button.setObjectName("importDialogClearSelection")
        self._clear_selection_button.setAutoDefault(False)
        self._clear_selection_button.clicked.connect(self._on_clear_selection)
        controls.addWidget(self._clear_selection_button)

        controls.addStretch(1)
        layout.addLayout(controls)

        self._scroll = QScrollArea(self)
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self._list_container = QWidget(self._scroll)
        self._list_layout = QVBoxLayout(self._list_container)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(6)
        self._scroll.setWidget(self._list_container)
        layout.addWidget(self._scroll, 1)

        self._summary_label = QLabel("", self)
        self._summary_label.setObjectName("importDialogSummary")
        self._summary_label.setWordWrap(True)
        layout.addWidget(self._summary_label)

        button_box = QDialogButtonBox(self)
        button_box.setObjectName("importDialogButtonBox")
        self._import_button = button_box.addButton(
            "Import", QDialogButtonBox.ButtonRole.AcceptRole
        )
        self._cancel_button = button_box.addButton(
            "Cancel", QDialogButtonBox.ButtonRole.RejectRole
        )
        self._import_button.setObjectName("importDialogImport")
        self._cancel_button.setObjectName("importDialogCancel")
        self._import_button.setAutoDefault(False)
        self._cancel_button.setAutoDefault(True)
        button_box.accepted.connect(self._on_accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        self._build_plan(default_mode)

    # ------------------------------------------------------------------
    # Plan construction
    # ------------------------------------------------------------------
    def _build_plan(self, mode: ImportMode) -> None:
        try:
            coordinator = self._coordinator_factory()
        except Exception as exc:  # noqa: BLE001 - boundary
            _logger.exception("Unable to construct the import coordinator")
            self._show_error(
                "Import unavailable",
                f"The import subsystem is unavailable: {exc}",
            )
            self._plan = None
            self._render_plan()
            return
        try:
            self._plan = coordinator.prepare(self._paths, mode)
        except ImportError as exc:
            self._show_error("Validation failed", str(exc))
            self._plan = None
        except Exception as exc:  # noqa: BLE001 - boundary
            _logger.exception("Unexpected error during import preparation")
            self._show_error("Validation failed", str(exc))
            self._plan = None
        self._render_plan()

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------
    def _render_plan(self) -> None:
        self._clear_rows()
        self._checkboxes.clear()

        if self._plan is None:
            placeholder = QLabel(
                "No files were selected.", self._list_container
            )
            placeholder.setObjectName("importDialogPlaceholder")
            self._list_layout.addWidget(placeholder)
            self._summary_label.setText("")
            self._import_button.setEnabled(False)
            return

        if not self._plan.candidates:
            placeholder = QLabel(
                "No files were selected.", self._list_container
            )
            placeholder.setObjectName("importDialogPlaceholder")
            self._list_layout.addWidget(placeholder)
            self._summary_label.setText("")
            self._import_button.setEnabled(False)
            return

        for candidate in self._plan.candidates:
            self._list_layout.addWidget(self._build_row(candidate))
        self._list_layout.addStretch(1)
        self._refresh_summary()

    def _build_row(self, candidate: ImportCandidate) -> QWidget:
        row = QFrame(self._list_container)
        row.setObjectName("importRow")
        row.setFrameShape(QFrame.Shape.StyledPanel)
        layout = QHBoxLayout(row)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)

        checkbox = QCheckBox(row)
        checkbox.setObjectName("importRowCheckbox")
        checkbox.setChecked(candidate.is_importable)
        checkbox.setEnabled(candidate.is_importable)
        checkbox.toggled.connect(self._refresh_summary)
        layout.addWidget(checkbox)
        self._checkboxes[candidate.source_path] = checkbox

        text_container = QWidget(row)
        text_layout = QVBoxLayout(text_container)
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(2)

        title = QLabel(candidate.filename or candidate.source_path.name, text_container)
        title.setObjectName("importRowTitle")
        title.setWordWrap(True)
        text_layout.addWidget(title)

        detail = QLabel(_detail_text(candidate), text_container)
        detail.setObjectName("importRowDetail")
        detail.setWordWrap(True)
        text_layout.addWidget(detail)

        layout.addWidget(text_container, 1)

        state = QLabel(_state_text(candidate.state), row)
        state.setObjectName("importRowState")
        state.setProperty("state", candidate.state.value)
        layout.addWidget(state)

        return row

    def _clear_rows(self) -> None:
        while self._list_layout.count():
            item = self._list_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

    def _refresh_summary(self) -> None:
        if self._plan is None:
            return
        selected = self._selected_paths()
        ready = sum(
            1
            for candidate in self._plan.candidates
            if candidate.state is ImportCandidateState.READY
            and candidate.source_path in selected
        )
        duplicates = sum(
            1
            for candidate in self._plan.candidates
            if candidate.state is ImportCandidateState.DUPLICATE
            and candidate.source_path in selected
        )
        blocked = self._plan.blocked_count
        self._summary_label.setText(
            f"{len(self._plan.candidates)} file(s) selected; "
            f"{ready} ready, {duplicates} duplicate(s), {blocked} blocked."
        )
        self._import_button.setEnabled(ready + duplicates > 0)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------
    def _on_mode_changed(self, _index: int) -> None:
        mode = self._current_mode()
        self._build_plan(mode)

    def _on_select_all(self) -> None:
        for checkbox in self._checkboxes.values():
            if checkbox.isEnabled():
                checkbox.setChecked(True)
        self._refresh_summary()

    def _on_clear_selection(self) -> None:
        for checkbox in self._checkboxes.values():
            checkbox.setChecked(False)
        self._refresh_summary()

    def _on_accept(self) -> None:
        if self._plan is None:
            self.reject()
            return
        selected = self._selected_paths()
        if not selected:
            self._show_error(
                "Nothing to import",
                "Select at least one file to import.",
            )
            return
        try:
            coordinator = self._coordinator_factory()
        except Exception as exc:  # noqa: BLE001 - boundary
            _logger.exception("Unable to construct the import coordinator")
            self._show_error("Import unavailable", str(exc))
            return

        QGuiApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            result = coordinator.import_files(
                self._plan,
                selected_paths=list(selected),
                import_duplicates=self._import_duplicates_checkbox.isChecked(),
            )
        except ImportError as exc:
            self._show_error("Import failed", str(exc))
            return
        except Exception as exc:  # noqa: BLE001 - boundary
            _logger.exception("Unexpected error during import")
            self._show_error("Import failed", str(exc))
            return
        finally:
            QGuiApplication.restoreOverrideCursor()

        self.imported.emit(result)
        if self._notification_service is not None:
            summary = (
                f"{result.imported_count} imported, "
                f"{result.skipped_count} skipped, "
                f"{result.failed_count} failed."
            )
            if result.failed_count:
                self._notification_service.warning("Import completed", summary)
            elif result.imported_count:
                self._notification_service.success("Import completed", summary)
            else:
                self._notification_service.info("Import completed", summary)
        self.accept()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _current_mode(self) -> ImportMode:
        data = self._mode_combo.currentData()
        try:
            return ImportMode(data)
        except (ValueError, TypeError):
            return ImportMode.MANAGED_COPY

    def _selected_paths(self) -> set[Path]:
        return {
            path for path, checkbox in self._checkboxes.items() if checkbox.isChecked()
        }

    def _show_error(self, title: str, message: str) -> None:
        DialogFactory.message(self, title, message, kind=MessageKind.ERROR)


# ----------------------------------------------------------------------
# Rendering helpers
# ----------------------------------------------------------------------
def _detail_text(candidate) -> str:
    parts: list[str] = []
    parts.append(str(candidate.source_path))
    if candidate.size_bytes is not None:
        parts.append(_format_bytes(candidate.size_bytes))
    if candidate.extension:
        parts.append(candidate.extension)
    if candidate.duplicate_signal:
        parts.append(f"match: {candidate.duplicate_signal}")
    if candidate.message:
        parts.append(candidate.message)
    return " · ".join(parts)

def _format_bytes(value: int) -> str:
    if value < 1024:
        return f"{value} B"
    if value < 1024 * 1024:
        return f"{value / 1024:.1f} KB"
    if value < 1024 * 1024 * 1024:
        return f"{value / (1024 * 1024):.1f} MB"
    return f"{value / (1024 * 1024 * 1024):.2f} GB"


def _state_text(state: ImportCandidateState) -> str:
    return {
        ImportCandidateState.READY: "Ready",
        ImportCandidateState.DUPLICATE: "Duplicate",
        ImportCandidateState.UNSUPPORTED: "Unsupported",
        ImportCandidateState.OVERSIZE: "Too large",
        ImportCandidateState.MISSING: "Missing",
        ImportCandidateState.UNREADABLE: "Unreadable",
        ImportCandidateState.ERROR: "Error",
    }.get(state, state.value)