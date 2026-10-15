"""Personal library page.

The page renders the user's documents in a table, provides a search bar
wired to the FTS5 query service, a filter panel for processing state
and extension, an import action, and a detail panel showing the
selected document's metadata and chunks.

Design decisions
----------------
- The page reads through the application-layer ``LibraryService``. It
  never touches the database or the filesystem directly.
- The list is rendered as a ``QTableView`` with a custom model. The
  model holds ``LibraryEntry`` instances and exposes the columns the
  user can sort by.
- The search bar is debounced: typing does not trigger a query on every
  keystroke. A short timer delays the actual search by a fixed
  interval.
- The detail panel is populated on selection. Its content is derived
  from the entry and, when requested, from the document's metadata row
  and chunks.
- The import action opens the shared import dialog. On completion, the
  page refreshes its listing.
- The page emits signals for actions that the shell wires to other
  destinations (for example, opening a document in the reader).
"""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QSortFilterProxyModel,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QSplitter,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from academic_platform.application.library.errors import (
    LibraryEntryNotFoundError,
    LibraryError,
)
from academic_platform.application.library.model import (
    LibraryEntry,
    LibraryFilter,
    LibrarySortDirection,
    LibrarySortField,
)
from academic_platform.application.library.service import LibraryService
from academic_platform.ui.components.empty_state import EmptyState
from academic_platform.ui.components.section_card import SectionCard
from academic_platform.ui.dialogs.confirm_dialog import ConfirmResult
from academic_platform.ui.dialogs.dialog_factory import DialogFactory
from academic_platform.ui.dialogs.message_dialog import MessageKind
from academic_platform.ui.main_window_destinations import get_destination
from academic_platform.ui.pages.base_page import BasePage

_logger = logging.getLogger(__name__)

_SEARCH_DEBOUNCE_MS = 300


class _LibraryTableModel(QAbstractTableModel):
    """Table model exposing ``LibraryEntry`` instances."""

    COLUMNS: tuple[tuple[str, str], ...] = (
        ("display_name", "Title"),
        ("authors", "Authors"),
        ("year", "Year"),
        ("extension", "Format"),
        ("size_bytes", "Size"),
        ("processing_state", "State"),
        ("updated_at", "Updated"),
    )

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._entries: list[LibraryEntry] = []

    # ------------------------------------------------------------------
    # QAbstractTableModel interface
    # ------------------------------------------------------------------
    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        if parent.isValid():
            return 0
        return len(self._entries)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        if parent.isValid():
            return 0
        return len(self.COLUMNS)

    def headerData(  # noqa: N802
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ):
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal:
            if 0 <= section < len(self.COLUMNS):
                return self.COLUMNS[section][1]
            return None
        return section + 1

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        if index.row() < 0 or index.row() >= len(self._entries):
            return None
        entry = self._entries[index.row()]
        column = self.COLUMNS[index.column()][0] if index.column() < len(self.COLUMNS) else ""
        if role == Qt.ItemDataRole.DisplayRole:
            return _display_value(entry, column)
        if role == Qt.ItemDataRole.ToolTipRole:
            return _tooltip_value(entry, column)
        if role == Qt.ItemDataRole.UserRole:
            return entry
        if role == Qt.ItemDataRole.TextAlignmentRole and column in {"year", "size_bytes"}:
            return int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        return None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def set_entries(self, entries: list[LibraryEntry]) -> None:
        self.beginResetModel()
        self._entries = list(entries)
        self.endResetModel()

    def entry_at(self, row: int) -> LibraryEntry | None:
        if 0 <= row < len(self._entries):
            return self._entries[row]
        return None

    @property
    def entries(self) -> tuple[LibraryEntry, ...]:
        return tuple(self._entries)


class LibraryPage(BasePage):
    """Personal library page."""

    #: Emitted when the user requests to open a document in the reader.
    open_document_requested = Signal(str)

    #: Emitted when the user requests to add a document to a collection.
    add_to_collection_requested = Signal(str)

    #: Emitted when the user requests to add a document to a project.
    add_to_project_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        destination = get_destination("library")
        super().__init__(
            title=destination.label,
            subtitle=destination.purpose,
            parent=parent,
        )
        self.setObjectName("libraryPage")

        self._service: LibraryService | None = None
        self._import_dialog_factory = None
        self._filter_state = LibraryFilter()
        self._sort_field = LibrarySortField.UPDATED_AT
        self._sort_direction = LibrarySortDirection.DESCENDING

        self._build_content()
        self._wire_header_actions()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def attach_service(self, service: LibraryService) -> None:
        """Attach the application-layer library service."""
        self._service = service
        self.refresh()

    def attach_import_factory(self, factory) -> None:
        """Attach the callable that opens the import dialog."""
        self._import_dialog_factory = factory

    def refresh(self) -> None:
        """Reload the library listing from the service."""
        if self._service is None:
            self._show_service_unavailable()
            return
        try:
            page = self._service.list_entries(
                filter_state=self._filter_state,
                sort_field=self._sort_field,
                sort_direction=self._sort_direction,
            )
        except LibraryError as exc:
            _logger.warning("Unable to load the library: %s", exc)
            self._show_error(str(exc))
            return
        self._model.set_entries(list(page.entries))
        self._update_summary(page.total)
        self._update_empty_state()
        self._clear_detail()

    # ------------------------------------------------------------------
    # Content construction
    # ------------------------------------------------------------------
    def _build_content(self) -> None:
        content = QWidget(self)
        content.setObjectName("libraryContent")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        layout.addWidget(self._build_search_row(content))
        layout.addWidget(self._build_filter_row(content))

        splitter = QSplitter(Qt.Orientation.Horizontal, content)
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(self._build_table(content))
        splitter.addWidget(self._build_detail_panel(content))
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([700, 400])
        layout.addWidget(splitter, 1)

        self._install_content(content)
        self._install_empty_state(
            EmptyState(
                title="No documents yet",
                message=(
                    "Import a PDF, book, or reference file to begin "
                    "building your library. Imported documents are "
                    "searchable and can be organized into collections."
                ),
                glyph="\u2261",
                parent=self,
            )
        )

    def _build_search_row(self, parent: QWidget) -> QWidget:
        container = QWidget(parent)
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self._search_input = QLineEdit(container)
        self._search_input.setObjectName("librarySearchInput")
        self._search_input.setPlaceholderText(
            "Search titles, authors, and document content…"
        )
        self._search_input.textChanged.connect(self._on_search_text_changed)
        self._search_input.returnPressed.connect(self._apply_search)
        layout.addWidget(self._search_input, 1)

        self._search_button = QPushButton("Search", container)
        self._search_button.setObjectName("librarySearchButton")
        self._search_button.setAutoDefault(False)
        self._search_button.clicked.connect(self._apply_search)
        layout.addWidget(self._search_button)

        self._clear_search_button = QPushButton("Clear", container)
        self._clear_search_button.setObjectName("librarySearchClear")
        self._clear_search_button.setAutoDefault(False)
        self._clear_search_button.clicked.connect(self._clear_search)
        layout.addWidget(self._clear_search_button)

        self._search_timer = QTimer(container)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(_SEARCH_DEBOUNCE_MS)
        self._search_timer.timeout.connect(self._apply_search)

        return container

    def _build_filter_row(self, parent: QWidget) -> QWidget:
        card = SectionCard("Filters", parent)
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self._filter_state_label = QLabel("No filters applied.", card)
        self._filter_state_label.setObjectName("libraryFilterState")
        layout.addWidget(self._filter_state_label, 1)

        self._reset_filters_button = QPushButton("Reset filters", card)
        self._reset_filters_button.setObjectName("libraryFilterReset")
        self._reset_filters_button.setAutoDefault(False)
        self._reset_filters_button.clicked.connect(self._reset_filters)
        layout.addWidget(self._reset_filters_button)

        card.set_content_layout(layout)
        return card

    def _build_table(self, parent: QWidget) -> QWidget:
        self._model = _LibraryTableModel(parent)
        self._proxy = QSortFilterProxyModel(parent)
        self._proxy.setSourceModel(self._model)
        self._proxy.setSortRole(Qt.ItemDataRole.DisplayRole)

        self._table = QTableView(parent)
        self._table.setObjectName("libraryTable")
        self._table.setModel(self._proxy)
        self._table.setSortingEnabled(False)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setAlternatingRowColors(True)
        self._table.setShowGrid(False)
        self._table.verticalHeader().setVisible(False)
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        self._table.selectionModel().currentRowChanged.connect(
            self._on_current_row_changed
        )
        self._table.doubleClicked.connect(self._on_double_clicked)
        self._table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._on_context_menu)
        return self._table

    def _build_detail_panel(self, parent: QWidget) -> QWidget:
        container = QWidget(parent)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        card = SectionCard("Document details", container)
        body = QWidget(card)
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(4)

        self._detail_title = QLabel("Select a document to view details.", body)
        self._detail_title.setObjectName("libraryDetailTitle")
        self._detail_title.setWordWrap(True)
        body_layout.addWidget(self._detail_title)

        self._detail_authors = QLabel("", body)
        self._detail_authors.setObjectName("libraryDetailAuthors")
        self._detail_authors.setWordWrap(True)
        body_layout.addWidget(self._detail_authors)

        self._detail_metadata = QLabel("", body)
        self._detail_metadata.setObjectName("libraryDetailMetadata")
        self._detail_metadata.setWordWrap(True)
        body_layout.addWidget(self._detail_metadata)

        self._detail_path = QLabel("", body)
        self._detail_path.setObjectName("libraryDetailPath")
        self._detail_path.setWordWrap(True)
        self._detail_path.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        body_layout.addWidget(self._detail_path)

        self._detail_error = QLabel("", body)
        self._detail_error.setObjectName("libraryDetailError")
        self._detail_error.setWordWrap(True)
        self._detail_error.setVisible(False)
        body_layout.addWidget(self._detail_error)

        card.set_content_widget(body)
        layout.addWidget(card)
        layout.addStretch(1)
        return container

    def _wire_header_actions(self) -> None:
        self._import_button = QPushButton("Import files…", self)
        self._import_button.setObjectName("libraryImportButton")
        self._import_button.setAutoDefault(False)
        self._import_button.clicked.connect(self._on_import)
        self.add_header_action(self._import_button)

        self._refresh_button = QPushButton("Refresh", self)
        self._refresh_button.setObjectName("libraryRefreshButton")
        self._refresh_button.setAutoDefault(False)
        self._refresh_button.clicked.connect(self.refresh)
        self.add_header_action(self._refresh_button)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------
    def _on_search_text_changed(self, _text: str) -> None:
        self._search_timer.start()

    def _apply_search(self) -> None:
        text = self._search_input.text().strip()
        self._filter_state = LibraryFilter(
            search_text=text,
            processing_states=self._filter_state.processing_states,
            extensions=self._filter_state.extensions,
        )
        self._update_filter_state_label()
        self.refresh()

    def _clear_search(self) -> None:
        self._search_timer.stop()
        self._search_input.clear()
        self._filter_state = LibraryFilter(
            search_text="",
            processing_states=self._filter_state.processing_states,
            extensions=self._filter_state.extensions,
        )
        self._update_filter_state_label()
        self.refresh()

    def _reset_filters(self) -> None:
        self._search_timer.stop()
        self._search_input.clear()
        self._filter_state = LibraryFilter()
        self._update_filter_state_label()
        self.refresh()

    def _on_current_row_changed(self, current: QModelIndex, _previous: QModelIndex) -> None:
        if not current.isValid():
            self._clear_detail()
            return
        source_index = self._proxy.mapToSource(current)
        entry = self._model.entry_at(source_index.row())
        if entry is None:
            self._clear_detail()
            return
        self._show_detail(entry)

    def _on_double_clicked(self, index: QModelIndex) -> None:
        if not index.isValid():
            return
        source_index = self._proxy.mapToSource(index)
        entry = self._model.entry_at(source_index.row())
        if entry is None:
            return
        self.open_document_requested.emit(entry.key)

    def _on_context_menu(self, position) -> None:
        index = self._table.indexAt(position)
        if not index.isValid():
            return
        source_index = self._proxy.mapToSource(index)
        entry = self._model.entry_at(source_index.row())
        if entry is None:
            return
        menu = QMenu(self._table)
        open_action = QAction("Open", menu)
        open_action.triggered.connect(
            lambda _checked=False, key=entry.key: self.open_document_requested.emit(key)
        )
        menu.addAction(open_action)
        collection_action = QAction("Add to collection…", menu)
        collection_action.triggered.connect(
            lambda _checked=False, key=entry.key: self.add_to_collection_requested.emit(key)
        )
        menu.addAction(collection_action)
        project_action = QAction("Add to project…", menu)
        project_action.triggered.connect(
            lambda _checked=False, key=entry.key: self.add_to_project_requested.emit(key)
        )
        menu.addAction(project_action)
        menu.addSeparator()
        mark_missing_action = QAction("Mark as missing", menu)
        mark_missing_action.triggered.connect(
            lambda _checked=False, key=entry.key: self._on_mark_missing(key)
        )
        menu.addAction(mark_missing_action)
        mark_present_action = QAction("Mark as present", menu)
        mark_present_action.triggered.connect(
            lambda _checked=False, key=entry.key: self._on_mark_present(key)
        )
        menu.addAction(mark_present_action)
        menu.addSeparator()
        delete_action = QAction("Remove from library…", menu)
        delete_action.triggered.connect(
            lambda _checked=False, key=entry.key: self._on_delete(key)
        )
        menu.addAction(delete_action)
        menu.exec(self._table.viewport().mapToGlobal(position))

    def _on_import(self) -> None:
        if self._import_dialog_factory is None:
            self._show_error("Import is not available in this session.")
            return
        try:
            self._import_dialog_factory(self)
        except Exception as exc:  # noqa: BLE001 - boundary
            _logger.exception("Unable to open the import dialog")
            self._show_error(f"Unable to open the import dialog: {exc}")
            return
        self.refresh()

    def _on_mark_missing(self, document_key: str) -> None:
        if self._service is None:
            return
        try:
            self._service.mark_missing(document_key)
        except LibraryError as exc:
            self._show_error(str(exc))
            return
        self.refresh()

    def _on_mark_present(self, document_key: str) -> None:
        if self._service is None:
            return
        try:
            self._service.mark_present(document_key)
        except LibraryError as exc:
            self._show_error(str(exc))
            return
        self.refresh()

    def _on_delete(self, document_key: str) -> None:
        outcome = DialogFactory.confirm(
            self,
            "Remove from library",
            (
                "Remove this document from the library? The underlying "
                "file is not deleted from disk."
            ),
            confirm_label="Remove",
            cancel_label="Cancel",
            destructive=True,
            default_to_confirm=False,
        )
        if outcome.result is not ConfirmResult.CONFIRMED:
            return
        if self._service is None:
            return
        try:
            self._service.delete_entry(document_key)
        except LibraryError as exc:
            self._show_error(str(exc))
            return
        self.refresh()

    # ------------------------------------------------------------------
    # Rendering helpers
    # ------------------------------------------------------------------
    def _show_detail(self, entry: LibraryEntry) -> None:
        self._detail_title.setText(entry.title or entry.display_name)
        if entry.authors:
            self._detail_authors.setText(", ".join(entry.authors))
        else:
            self._detail_authors.setText("")
        parts: list[str] = []
        if entry.year is not None:
            parts.append(f"Year: {entry.year}")
        if entry.doi:
            parts.append(f"DOI: {entry.doi}")
        parts.append(f"Format: {entry.extension or 'unknown'}")
        parts.append(f"Size: {_format_bytes(entry.size_bytes)}")
        parts.append(f"Storage: {_storage_mode_label(entry.storage_mode)}")
        parts.append(f"State: {entry.processing_state}")
        if entry.page_count:
            parts.append(f"Pages: {entry.page_count}")
        if entry.ocr_state != "not_required":
            parts.append(f"OCR: {entry.ocr_state}")
        if entry.missing:
            parts.append("Missing on disk")
        self._detail_metadata.setText(" · ".join(parts))
        self._detail_path.setText(entry.location)
        if entry.last_error:
            self._detail_error.setText(entry.last_error)
            self._detail_error.setVisible(True)
        else:
            self._detail_error.setText("")
            self._detail_error.setVisible(False)

    def _clear_detail(self) -> None:
        self._detail_title.setText("Select a document to view details.")
        self._detail_authors.setText("")
        self._detail_metadata.setText("")
        self._detail_path.setText("")
        self._detail_error.setText("")
        self._detail_error.setVisible(False)

    def _update_summary(self, total: int) -> None:
        self.set_subtitle(
            f"{total} document(s) in the library."
            if total
            else "No documents in the library."
        )

    def _update_filter_state_label(self) -> None:
        parts: list[str] = []
        if self._filter_state.search_text:
            parts.append(f"search: {self._filter_state.search_text!r}")
        if self._filter_state.processing_states:
            parts.append(
                "state: "
                + ", ".join(sorted(self._filter_state.processing_states))
            )
        if self._filter_state.extensions:
            parts.append(
                "format: "
                + ", ".join(sorted(self._filter_state.extensions))
            )
        self._filter_state_label.setText(
            " · ".join(parts) if parts else "No filters applied."
        )

    def _update_empty_state(self) -> None:
        if self._model.rowCount() == 0:
            self.show_empty_state()
        else:
            self.show_content()

    def _show_service_unavailable(self) -> None:
        self._model.set_entries([])
        self._update_empty_state()

    def _show_error(self, message: str) -> None:
        DialogFactory.message(
            self,
            "Library error",
            message,
            kind=MessageKind.ERROR,
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def on_activated(self) -> None:
        self.refresh()


# ----------------------------------------------------------------------
# Rendering helpers
# ----------------------------------------------------------------------
def _display_value(entry: LibraryEntry, column: str) -> str:
    if column == "display_name":
        return entry.title or entry.display_name
    if column == "authors":
        return ", ".join(entry.authors) if entry.authors else "—"
    if column == "year":
        return str(entry.year) if entry.year is not None else "—"
    if column == "extension":
        return entry.extension or "—"
    if column == "size_bytes":
        return _format_bytes(entry.size_bytes)
    if column == "processing_state":
        return entry.processing_state
    if column == "updated_at":
        return entry.updated_at[:19].replace("T", " ") if entry.updated_at else "—"
    return ""


def _tooltip_value(entry: LibraryEntry, column: str) -> str:
    if column == "display_name":
        return entry.location
    if column == "processing_state":
        return entry.last_error or entry.processing_state
    return ""


def _format_bytes(value: int) -> str:
    if value < 1024:
        return f"{value} B"
    if value < 1024 * 1024:
        return f"{value / 1024:.1f} KB"
    if value < 1024 * 1024 * 1024:
        return f"{value / (1024 * 1024):.1f} MB"
    return f"{value / (1024 * 1024 * 1024):.2f} GB"


def _storage_mode_label(mode: str) -> str:
    if mode == "managed_copy":
        return "Managed copy"
    if mode == "referenced_file":
        return "Referenced file"
    return mode