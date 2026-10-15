"""Saved searches panel for the Discover page.

The panel displays the user's saved searches and exposes actions for
opening a saved search (which populates the search bar), executing it,
renaming it, and removing it. It is embedded in the Discover page below
the search bar and above the results tabs.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from academic_platform.application.saved_searches.errors import (
    SavedSearchError,
    SavedSearchNotFoundError,
)
from academic_platform.application.saved_searches.model import SavedSearch
from academic_platform.application.saved_searches.service import (
    SavedSearchService,
)
from academic_platform.ui.dialogs.confirm_dialog import ConfirmResult
from academic_platform.ui.dialogs.dialog_factory import DialogFactory
from academic_platform.ui.dialogs.message_dialog import MessageKind
from academic_platform.ui.notifications.service import NotificationService

_logger = logging.getLogger(__name__)


class SavedSearchesPanel(QFrame):
    """Panel listing saved searches with per-search actions."""

    #: Emitted when the user requests to load a saved search into the
    #: search bar without executing it. Carries the search.
    load_requested = Signal(object)

    #: Emitted when the user requests to execute a saved search. Carries
    #: the search.
    execute_requested = Signal(object)

    def __init__(
        self,
        service_factory,
        *,
        notification_service: NotificationService | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("savedSearchesPanel")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self._service_factory = service_factory
        self._notification_service = notification_service

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 12)
        layout.setSpacing(6)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(8)

        title = QLabel("Saved searches", self)
        title.setObjectName("savedSearchesTitle")
        header.addWidget(title, 1)

        self._refresh_button = QPushButton("Refresh", self)
        self._refresh_button.setObjectName("savedSearchesRefresh")
        self._refresh_button.setAutoDefault(False)
        self._refresh_button.clicked.connect(self.refresh)
        header.addWidget(self._refresh_button)

        layout.addLayout(header)

        self._list_container = QWidget(self)
        self._list_layout = QVBoxLayout(self._list_container)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(4)
        layout.addWidget(self._list_container)

        self._empty_label = QLabel(
            "No saved searches yet. Save a search to reuse it later.",
            self,
        )
        self._empty_label.setObjectName("savedSearchesEmpty")
        self._empty_label.setWordWrap(True)
        layout.addWidget(self._empty_label)

        self.refresh()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def refresh(self) -> None:
        """Reload the saved-search list from the service."""
        self._clear_rows()
        service = self._get_service()
        if service is None:
            self._empty_label.setText("Saved-search service is unavailable.")
            self._empty_label.setVisible(True)
            return
        try:
            searches = service.list_all()
        except SavedSearchError as exc:
            _logger.warning("Unable to list saved searches: %s", exc)
            self._empty_label.setText("Unable to read saved searches.")
            self._empty_label.setVisible(True)
            return
        if not searches:
            self._empty_label.setVisible(True)
            return
        self._empty_label.setVisible(False)
        for search in searches:
            self._list_layout.addWidget(self._build_row(search))

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _get_service(self) -> SavedSearchService | None:
        try:
            return self._service_factory()
        except Exception:  # noqa: BLE001 - defensive boundary
            _logger.exception("Unable to construct the saved-search service")
            return None

    def _build_row(self, search: SavedSearch) -> QWidget:
        row = QFrame(self._list_container)
        row.setObjectName("savedSearchRow")
        row.setFrameShape(QFrame.Shape.NoFrame)
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        label = QLabel(search.display_label, row)
        label.setObjectName("savedSearchLabel")
        label.setWordWrap(True)
        layout.addWidget(label, 1)

        scope_label = QLabel(search.scope, row)
        scope_label.setObjectName("savedSearchScope")
        layout.addWidget(scope_label)

        load_button = QPushButton("Load", row)
        load_button.setObjectName("savedSearchLoad")
        load_button.setAutoDefault(False)
        load_button.clicked.connect(
            lambda _checked=False, s=search: self.load_requested.emit(s)
        )
        layout.addWidget(load_button)

        execute_button = QPushButton("Run", row)
        execute_button.setObjectName("savedSearchRun")
        execute_button.setAutoDefault(False)
        execute_button.clicked.connect(
            lambda _checked=False, s=search: self._on_execute(s)
        )
        layout.addWidget(execute_button)

        rename_button = QPushButton("Rename", row)
        rename_button.setObjectName("savedSearchRename")
        rename_button.setAutoDefault(False)
        rename_button.clicked.connect(
            lambda _checked=False, s=search: self._on_rename(s)
        )
        layout.addWidget(rename_button)

        remove_button = QPushButton("Remove", row)
        remove_button.setObjectName("savedSearchRemove")
        remove_button.setAutoDefault(False)
        remove_button.clicked.connect(
            lambda _checked=False, s=search: self._on_remove(s)
        )
        layout.addWidget(remove_button)
        return row

    def _clear_rows(self) -> None:
        while self._list_layout.count():
            item = self._list_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------
    def _on_execute(self, search: SavedSearch) -> None:
        service = self._get_service()
        if service is None:
            self._show_error("Saved-search service unavailable", "")
            return
        try:
            service.mark_executed(search.key)
        except SavedSearchNotFoundError:
            self._show_error("Saved search not found", search.key)
            return
        except SavedSearchError as exc:
            self._show_error("Unable to update saved search", str(exc))
            return
        self.execute_requested.emit(search)

    def _on_rename(self, search: SavedSearch) -> None:
        service = self._get_service()
        if service is None:
            self._show_error("Saved-search service unavailable", "")
            return
        new_name = DialogFactory.prompt(
            self,
            "Rename saved search",
            "Name",
            initial=search.name or search.display_label,
        )
        if new_name is None:
            return
        trimmed = new_name.strip()
        try:
            service.update(search.key, name=trimmed)
        except SavedSearchError as exc:
            self._show_error("Unable to rename saved search", str(exc))
            return
        self._notify("Saved search renamed", trimmed)
        self.refresh()

    def _on_remove(self, search: SavedSearch) -> None:
        service = self._get_service()
        if service is None:
            self._show_error("Saved-search service unavailable", "")
            return
        outcome = DialogFactory.confirm(
            self,
            "Remove saved search",
            f"Remove the saved search {search.display_label!r}?",
            confirm_label="Remove",
            cancel_label="Cancel",
            destructive=True,
            default_to_confirm=False,
        )
        if outcome.result is not ConfirmResult.CONFIRMED:
            return
        try:
            service.delete(search.key)
        except SavedSearchError as exc:
            self._show_error("Unable to remove saved search", str(exc))
            return
        self._notify("Saved search removed", search.display_label)
        self.refresh()

    def _show_error(self, title: str, message: str) -> None:
        DialogFactory.message(self, title, message, kind=MessageKind.ERROR)

    def _notify(self, title: str, message: str) -> None:
        if self._notification_service is None:
            return
        self._notification_service.success(title, message)