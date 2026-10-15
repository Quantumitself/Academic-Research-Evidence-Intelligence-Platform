"""Helper that opens the import dialog from any page.

The helper is a thin wrapper around ``ImportDialog``. It collects the
selected paths through a platform file dialog, constructs the dialog,
and connects the completion signal to the caller's callback. It is
shared between the Library page and, later, other pages that offer an
import action.

Design decisions
----------------
- The helper is a plain function, not a widget. Callers invoke it with
  the parent widget, the coordinator factory, and an optional
  notification service.
- The platform file dialog is restricted to PDFs at this stage of the
  product. The restriction matches the coordinator's supported extension
  set. The picker allows multiple files.
- The helper never performs the import itself. It delegates to the
  dialog and, through the dialog, to the application-layer coordinator.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path

from PySide6.QtWidgets import QFileDialog, QWidget

from academic_platform.application.library_import.coordinator import (
    ImportCoordinator,
)
from academic_platform.application.library_import.model import ImportMode
from academic_platform.ui.dialogs.import_dialog import ImportDialog
from academic_platform.ui.notifications.service import NotificationService

_logger = logging.getLogger(__name__)


def open_import_dialog(
    parent: QWidget | None,
    coordinator_factory: Callable[[], ImportCoordinator],
    *,
    default_mode: ImportMode = ImportMode.MANAGED_COPY,
    notification_service: NotificationService | None = None,
    on_imported: Callable[[object], None] | None = None,
) -> ImportDialog | None:
    """Open the platform picker and, when files are chosen, the import dialog.

    Returns the ``ImportDialog`` instance when the platform picker
    returned at least one file, or ``None`` when the user cancelled the
    picker. The caller may connect additional signals to the returned
    dialog before it is shown.
    """
    paths = _pick_files(parent)
    if not paths:
        return None
    dialog = ImportDialog(
        coordinator_factory=coordinator_factory,
        paths=paths,
        default_mode=default_mode,
        notification_service=notification_service,
        parent=parent,
    )
    if on_imported is not None:
        dialog.imported.connect(on_imported)
    dialog.exec()
    return dialog


def _pick_files(parent: QWidget | None) -> list[Path]:
    filters = "Documents (*.pdf);;All files (*)"
    selected, _ = QFileDialog.getOpenFileNames(
        parent,
        "Import documents",
        "",
        filters,
    )
    return [Path(path) for path in selected if path]