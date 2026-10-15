"""Collections page.

The page lists collections in a table, supports creation and editing
through the standard form dialog, exposes a detail panel with the
collection's items, and hosts item actions.

Design decisions
----------------
- The page reads and writes through the application-layer
  ``CollectionService``. It never touches the database directly.
- The list is rendered as a ``QTableView`` with a custom model. The
  model holds ``CollectionView`` instances and exposes the columns the
  user can sort by.
- The detail panel is populated on selection. It renders the
  collection's items and exposes actions to add, edit, remove, and
  reorder them.
- Creation and editing use the standard form dialog from the dialogs
  package. The form fields mirror the service's accepted parameters.
- Smart and saved-search collections expose a JSON filter editor. The
  service validates the payload's shape; the page does not interpret
  it.
- Smart collections compute their items from their filter. The items
  tab is read-only for smart collections and carries a hint explaining
  why; the item actions are disabled.
- Destructive actions are guarded by a confirmation prompt with a
  non-destructive default.
"""

from __future__ import annotations

import json
import logging

from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QSortFilterProxyModel,
    Qt,
    Signal,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QTableView,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from academic_platform.application.collections.errors import (
    CollectionError,
    CollectionNotFoundError,
    CollectionValidationError,
)
from academic_platform.application.collections.model import (
    CollectionItemView,
    CollectionKind,
    CollectionView,
)
from academic_platform.application.collections.service import CollectionService
from academic_platform.ui.components.empty_state import EmptyState
from academic_platform.ui.components.section_card import SectionCard
from academic_platform.ui.dialogs.confirm_dialog import ConfirmResult
from academic_platform.ui.dialogs.dialog_factory import DialogFactory
from academic_platform.ui.dialogs.form_dialog import FormField, FormFieldKind
from academic_platform.ui.dialogs.message_dialog import MessageKind
from academic_platform.ui.main_window_destinations import get_destination
from academic_platform.ui.pages.base_page import BasePage

_logger = logging.getLogger(__name__)

_ITEM_TYPES: tuple[tuple[str, str], ...] = (
    ("publication", "Publication"),
    ("document", "Document"),
    ("evidence", "Evidence record"),
    ("note", "Note"),
)


class _CollectionsTableModel(QAbstractTableModel):
    """Table model exposing ``CollectionView`` instances."""

    COLUMNS: tuple[tuple[str, str], ...] = (
        ("title", "Title"),
        ("kind", "Kind"),
        ("items", "Items"),
        ("project", "Project"),
        ("updated_at", "Updated"),
    )

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._collections: list[CollectionView] = []

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        if parent.isValid():
            return 0
        return len(self._collections)

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
        if index.row() < 0 or index.row() >= len(self._collections):
            return None
        collection = self._collections[index.row()]
        column = (
            self.COLUMNS[index.column()][0]
            if index.column() < len(self.COLUMNS)
            else ""
        )
        if role == Qt.ItemDataRole.DisplayRole:
            return _display_value(collection, column)
        if role == Qt.ItemDataRole.ToolTipRole:
            return _tooltip_value(collection, column)
        if role == Qt.ItemDataRole.UserRole:
            return collection
        if role == Qt.ItemDataRole.TextAlignmentRole and column == "items":
            return int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        return None

    def set_collections(self, collections: list[CollectionView]) -> None:
        self.beginResetModel()
        self._collections = list(collections)
        self.endResetModel()

    def collection_at(self, row: int) -> CollectionView | None:
        if 0 <= row < len(self._collections):
            return self._collections[row]
        return None

    @property
    def collections(self) -> tuple[CollectionView, ...]:
        return tuple(self._collections)


class CollectionsPage(BasePage):
    """Collections page."""

    #: Emitted when the user requests to open a document from the
    #: collection's items.
    open_document_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        destination = get_destination("collections")
        super().__init__(
            title=destination.label,
            subtitle=destination.purpose,
            parent=parent,
        )
        self.setObjectName("collectionsPage")

        self._service: CollectionService | None = None
        self._current_collection_key: str | None = None

        self._build_content()
        self._install_empty_state(
            EmptyState(
                title="No collections yet",
                message=(
                    "Create a collection to group related papers, "
                    "documents, and evidence records."
                ),
                glyph="\u25A4",
                action_label="Create a collection",
                parent=self,
            )
        )
        self._enable_empty_action()
        self._wire_header_actions()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def attach_service(self, service: CollectionService) -> None:
        """Attach the application-layer collection service."""
        self._service = service
        self.refresh()

    def refresh(self) -> None:
        """Reload the collection list from the service."""
        if self._service is None:
            self._model.set_collections([])
            self._update_empty_state()
            return
        try:
            collections = self._service.list_collections()
        except CollectionError as exc:
            _logger.warning("Unable to load collections: %s", exc)
            self._show_error(str(exc))
            return
        self._model.set_collections(collections)
        self._update_summary(len(collections))
        self._update_empty_state()
        if self._current_collection_key is not None:
            self._select_by_key(self._current_collection_key)
        else:
            self._clear_detail()

    # ------------------------------------------------------------------
    # Content construction
    # ------------------------------------------------------------------
    def _build_content(self) -> None:
        content = QWidget(self)
        content.setObjectName("collectionsContent")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        splitter = QSplitter(Qt.Orientation.Horizontal, content)
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(self._build_table(content))
        splitter.addWidget(self._build_detail_panel(content))
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([720, 420])
        layout.addWidget(splitter, 1)

        self._install_content(content)

    def _build_table(self, parent: QWidget) -> QWidget:
        container = QWidget(parent)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        filter_row = QHBoxLayout()
        filter_row.setContentsMargins(0, 0, 0, 0)
        filter_row.setSpacing(8)

        filter_label = QLabel("Show kind:", parent)
        filter_label.setObjectName("collectionsFilterLabel")
        filter_row.addWidget(filter_label)

        self._kind_filter = QComboBox(parent)
        self._kind_filter.setObjectName("collectionsKindFilter")
        self._kind_filter.addItem("All kinds", "")
        for kind in CollectionKind:
            self._kind_filter.addItem(kind.display_name, kind.value)
        self._kind_filter.currentIndexChanged.connect(self._on_filter_changed)
        filter_row.addWidget(self._kind_filter)

        filter_row.addStretch(1)
        layout.addLayout(filter_row)

        self._model = _CollectionsTableModel(container)
        self._proxy = QSortFilterProxyModel(container)
        self._proxy.setSourceModel(self._model)
        self._proxy.setSortRole(Qt.ItemDataRole.DisplayRole)

        self._table = QTableView(container)
        self._table.setObjectName("collectionsTable")
        self._table.setModel(self._proxy)
        self._table.setSortingEnabled(False)
        self._table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self._table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self._table.setAlternatingRowColors(True)
        self._table.setShowGrid(False)
        self._table.verticalHeader().setVisible(False)
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for column in range(1, len(_CollectionsTableModel.COLUMNS)):
            header.setSectionResizeMode(
                column, QHeaderView.ResizeMode.ResizeToContents
            )
        self._table.selectionModel().currentRowChanged.connect(
            self._on_current_row_changed
        )
        self._table.doubleClicked.connect(self._on_double_clicked)
        self._table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._on_context_menu)
        layout.addWidget(self._table, 1)

        return container

    def _build_detail_panel(self, parent: QWidget) -> QWidget:
        container = QWidget(parent)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        header_card = SectionCard("Collection details", container)
        header_body = QWidget(header_card)
        header_layout = QVBoxLayout(header_body)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(6)

        self._detail_title = QLabel(
            "Select a collection to view details.", header_body
        )
        self._detail_title.setObjectName("collectionsDetailTitle")
        self._detail_title.setWordWrap(True)
        header_layout.addWidget(self._detail_title)

        self._detail_description = QLabel("", header_body)
        self._detail_description.setObjectName("collectionsDetailDescription")
        self._detail_description.setWordWrap(True)
        header_layout.addWidget(self._detail_description)

        self._detail_summary = QLabel("", header_body)
        self._detail_summary.setObjectName("collectionsDetailSummary")
        self._detail_summary.setWordWrap(True)
        header_layout.addWidget(self._detail_summary)

        header_card.set_content_widget(header_body)
        layout.addWidget(header_card)

        self._detail_tabs = QTabWidget(container)
        self._detail_tabs.setObjectName("collectionsDetailTabs")

        self._items_tab = self._build_items_tab()
        self._filter_tab = self._build_filter_tab()
        self._detail_tabs.addTab(self._items_tab, "Items")
        self._detail_tabs.addTab(self._filter_tab, "Filter")
        layout.addWidget(self._detail_tabs, 1)

        return container

    def _build_items_tab(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(6)

        self._add_item_button = QPushButton("Add item", container)
        self._add_item_button.setObjectName("collectionsAddItem")
        self._add_item_button.setAutoDefault(False)
        self._add_item_button.setEnabled(False)
        self._add_item_button.clicked.connect(self._on_add_item)
        actions.addWidget(self._add_item_button)

        self._edit_item_button = QPushButton("Edit note", container)
        self._edit_item_button.setObjectName("collectionsEditItemNote")
        self._edit_item_button.setAutoDefault(False)
        self._edit_item_button.setEnabled(False)
        self._edit_item_button.clicked.connect(self._on_edit_item_note)
        actions.addWidget(self._edit_item_button)

        self._move_up_button = QPushButton("Move up", container)
        self._move_up_button.setObjectName("collectionsMoveUp")
        self._move_up_button.setAutoDefault(False)
        self._move_up_button.setEnabled(False)
        self._move_up_button.clicked.connect(self._on_move_item_up)
        actions.addWidget(self._move_up_button)

        self._move_down_button = QPushButton("Move down", container)
        self._move_down_button.setObjectName("collectionsMoveDown")
        self._move_down_button.setAutoDefault(False)
        self._move_down_button.setEnabled(False)
        self._move_down_button.clicked.connect(self._on_move_item_down)
        actions.addWidget(self._move_down_button)

        self._remove_item_button = QPushButton("Remove", container)
        self._remove_item_button.setObjectName("collectionsRemoveItem")
        self._remove_item_button.setAutoDefault(False)
        self._remove_item_button.setEnabled(False)
        self._remove_item_button.clicked.connect(self._on_remove_item)
        actions.addWidget(self._remove_item_button)

        actions.addStretch(1)
        layout.addLayout(actions)

        self._items_hint = QLabel("", container)
        self._items_hint.setObjectName("collectionsItemsHint")
        self._items_hint.setWordWrap(True)
        self._items_hint.hide()
        layout.addWidget(self._items_hint)

        self._items_list = QListWidget(container)
        self._items_list.setObjectName("collectionsItemsList")
        self._items_list.currentItemChanged.connect(self._on_item_selected)
        self._items_list.itemDoubleClicked.connect(
            lambda _item: self._on_edit_item_note()
        )
        layout.addWidget(self._items_list, 1)

        return container

    def _build_filter_tab(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        hint = QLabel(
            "Smart and saved-search collections carry a JSON filter "
            "payload. The filter is a JSON object describing the "
            "collection's rule.",
            container,
        )
        hint.setObjectName("collectionsFilterHint")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self._filter_editor = QPlainTextEdit(container)
        self._filter_editor.setObjectName("collectionsFilterEditor")
        self._filter_editor.setPlaceholderText('{"year_from": 2020}')
        self._filter_editor.setEnabled(False)
        layout.addWidget(self._filter_editor, 1)

        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(6)

        self._save_filter_button = QPushButton("Save filter", container)
        self._save_filter_button.setObjectName("collectionsSaveFilter")
        self._save_filter_button.setAutoDefault(False)
        self._save_filter_button.setEnabled(False)
        self._save_filter_button.clicked.connect(self._on_save_filter)
        actions.addWidget(self._save_filter_button)

        actions.addStretch(1)
        layout.addLayout(actions)

        return container

    def _wire_header_actions(self) -> None:
        self._create_button = QPushButton("New collection", self)
        self._create_button.setObjectName("collectionsCreateButton")
        self._create_button.setAutoDefault(False)
        self._create_button.clicked.connect(self._on_create_collection)
        self.add_header_action(self._create_button)

        self._edit_button = QPushButton("Edit collection", self)
        self._edit_button.setObjectName("collectionsEditButton")
        self._edit_button.setAutoDefault(False)
        self._edit_button.setEnabled(False)
        self._edit_button.clicked.connect(self._on_edit_collection)
        self.add_header_action(self._edit_button)

        self._refresh_button = QPushButton("Refresh", self)
        self._refresh_button.setObjectName("collectionsRefreshButton")
        self._refresh_button.setAutoDefault(False)
        self._refresh_button.clicked.connect(self.refresh)
        self.add_header_action(self._refresh_button)

    def _enable_empty_action(self) -> None:
        from academic_platform.ui.components.empty_state import EmptyState

        for widget in self.findChildren(EmptyState):
            widget.set_action("Create a collection", enabled=True)
            widget.action_requested.connect(self._on_create_collection)
            break

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------
    def _on_filter_changed(self, _index: int) -> None:
        kind_value = self._kind_filter.currentData() or ""
        collections = self._model.collections
        if kind_value:
            filtered = [c for c in collections if c.kind.value == kind_value]
        else:
            filtered = list(collections)
        self._model.set_collections(filtered)
        self._update_summary(len(filtered))
        self._update_empty_state()

    def _on_current_row_changed(
        self,
        current: QModelIndex,
        _previous: QModelIndex,
    ) -> None:
        if not current.isValid():
            self._clear_detail()
            return
        source_index = self._proxy.mapToSource(current)
        collection = self._model.collection_at(source_index.row())
        if collection is None:
            self._clear_detail()
            return
        self._show_detail(collection)

    def _on_double_clicked(self, index: QModelIndex) -> None:
        if not index.isValid():
            return
        source_index = self._proxy.mapToSource(index)
        collection = self._model.collection_at(source_index.row())
        if collection is None:
            return
        self._show_detail(collection)

    def _on_context_menu(self, position) -> None:
        index = self._table.indexAt(position)
        if not index.isValid():
            return
        source_index = self._proxy.mapToSource(index)
        collection = self._model.collection_at(source_index.row())
        if collection is None:
            return
        menu = QMenu(self._table)

        edit_action = menu.addAction("Edit…")
        edit_action.triggered.connect(
            lambda _checked=False, key=collection.key: self._edit_collection_by_key(
                key
            )
        )
        menu.addSeparator()
        delete_action = menu.addAction("Delete…")
        delete_action.triggered.connect(
            lambda _checked=False, key=collection.key: self._delete_collection_by_key(
                key
            )
        )
        menu.exec(self._table.viewport().mapToGlobal(position))

    def _on_create_collection(self) -> None:
        if self._service is None:
            self._show_error("The collection service is not attached.")
            return
        fields = (
            FormField(
                identifier="key",
                label="Collection key",
                kind=FormFieldKind.TEXT,
                placeholder="lowercase-with-hyphens",
                validator=_validate_collection_key,
            ),
            FormField(
                identifier="title",
                label="Title",
                kind=FormFieldKind.TEXT,
                validator=_validate_optional_length(512),
            ),
            FormField(
                identifier="description",
                label="Description",
                kind=FormFieldKind.MULTILINE,
                validator=_validate_optional_length(4096),
            ),
            FormField(
                identifier="kind",
                label="Kind",
                kind=FormFieldKind.SELECT,
                options=tuple(
                    (kind.value, kind.display_name) for kind in CollectionKind
                ),
                initial=CollectionKind.MANUAL.value,
            ),
            FormField(
                identifier="filter_json",
                label="Filter (JSON object)",
                kind=FormFieldKind.MULTILINE,
                placeholder='{"year_from": 2020}',
                help_text=(
                    "Required for smart and saved-search collections. "
                    "Ignored otherwise."
                ),
            ),
        )
        values = DialogFactory.form(
            self,
            "New collection",
            fields,
            submit_label="Create",
            cancel_label="Cancel",
        )
        if values is None:
            return
        try:
            kind = CollectionKind(
                str(values.get("kind") or CollectionKind.MANUAL.value)
            )
        except ValueError:
            kind = CollectionKind.MANUAL
        filter_json = str(values.get("filter_json") or "").strip() or None
        try:
            view = self._service.create_collection(
                key=str(values.get("key") or "").strip(),
                title=str(values.get("title") or "").strip(),
                description=str(values.get("description") or "").strip(),
                kind=kind,
                filter_json=filter_json,
            )
        except CollectionValidationError as exc:
            self._show_error("; ".join(exc.issues))
            return
        except CollectionError as exc:
            self._show_error(str(exc))
            return
        self._current_collection_key = view.key
        self.refresh()
        self._select_by_key(view.key)

    def _on_edit_collection(self) -> None:
        if self._current_collection_key is None:
            return
        self._edit_collection_by_key(self._current_collection_key)

    def _edit_collection_by_key(self, key: str) -> None:
        if self._service is None:
            return
        try:
            collection = self._service.get_collection(key)
        except CollectionError as exc:
            self._show_error(str(exc))
            return
        if collection.is_project_linked:
            self._show_error(
                "Project-linked collections are edited through the project's "
                "page and the document linking workflow."
            )
            return
        fields = (
            FormField(
                identifier="title",
                label="Title",
                kind=FormFieldKind.TEXT,
                initial=collection.title,
                validator=_validate_optional_length(512),
            ),
            FormField(
                identifier="description",
                label="Description",
                kind=FormFieldKind.MULTILINE,
                initial=collection.description,
                validator=_validate_optional_length(4096),
            ),
        )
        values = DialogFactory.form(
            self,
            f"Edit collection: {collection.display_label}",
            fields,
            submit_label="Save",
            cancel_label="Cancel",
        )
        if values is None:
            return
        try:
            self._service.update_collection(
                key,
                title=str(values.get("title") or "").strip(),
                description=str(values.get("description") or "").strip(),
            )
        except CollectionValidationError as exc:
            self._show_error("; ".join(exc.issues))
            return
        except CollectionError as exc:
            self._show_error(str(exc))
            return
        self.refresh()
        self._select_by_key(key)

    def _delete_collection_by_key(self, key: str) -> None:
        outcome = DialogFactory.confirm(
            self,
            "Delete collection",
            (
                "Delete this collection and its items? The referenced "
                "documents, publications, and evidence records are not "
                "deleted."
            ),
            confirm_label="Delete",
            cancel_label="Cancel",
            destructive=True,
            default_to_confirm=False,
        )
        if outcome.result is not ConfirmResult.CONFIRMED:
            return
        if self._service is None:
            return
        try:
            self._service.delete_collection(key)
        except CollectionError as exc:
            self._show_error(str(exc))
            return
        if self._current_collection_key == key:
            self._current_collection_key = None
        self.refresh()

    # ------------------------------------------------------------------
    # Item actions
    # ------------------------------------------------------------------
    def _on_add_item(self) -> None:
        if self._service is None or self._current_collection_key is None:
            return
        fields = (
            FormField(
                identifier="item_type",
                label="Item type",
                kind=FormFieldKind.SELECT,
                options=_ITEM_TYPES,
                initial="publication",
            ),
            FormField(
                identifier="item_identifier",
                label="Identifier",
                kind=FormFieldKind.TEXT,
                placeholder="publication key, document key, evidence id, or note id",
                validator=_validate_required("Identifier"),
            ),
            FormField(
                identifier="note",
                label="Note",
                kind=FormFieldKind.MULTILINE,
                placeholder="Optional note about this item.",
                validator=_validate_optional_length(2048),
            ),
        )
        values = DialogFactory.form(
            self,
            "Add item to collection",
            fields,
            submit_label="Add",
            cancel_label="Cancel",
        )
        if values is None:
            return
        try:
            self._service.add_item(
                self._current_collection_key,
                item_type=str(values.get("item_type") or "publication"),
                item_identifier=str(values.get("item_identifier") or "").strip(),
                note=str(values.get("note") or "").strip(),
            )
        except CollectionValidationError as exc:
            self._show_error("; ".join(exc.issues))
            return
        except CollectionError as exc:
            self._show_error(str(exc))
            return
        self._reload_items()

    def _on_edit_item_note(self) -> None:
        if self._service is None or self._current_collection_key is None:
            return
        item = self._items_list.currentItem()
        if item is None:
            return
        entry = item.data(Qt.ItemDataRole.UserRole)
        if entry is None:
            return
        fields = (
            FormField(
                identifier="note",
                label="Note",
                kind=FormFieldKind.MULTILINE,
                initial=entry.note,
                validator=_validate_optional_length(2048),
            ),
        )
        values = DialogFactory.form(
            self,
            "Edit item note",
            fields,
            submit_label="Save",
            cancel_label="Cancel",
        )
        if values is None:
            return
        try:
            self._service.update_item(
                self._current_collection_key,
                entry.identifier,
                note=str(values.get("note") or "").strip(),
            )
        except CollectionValidationError as exc:
            self._show_error("; ".join(exc.issues))
            return
        except CollectionError as exc:
            self._show_error(str(exc))
            return
        self._reload_items()

    def _on_remove_item(self) -> None:
        if self._service is None or self._current_collection_key is None:
            return
        item = self._items_list.currentItem()
        if item is None:
            return
        entry = item.data(Qt.ItemDataRole.UserRole)
        if entry is None:
            return
        outcome = DialogFactory.confirm(
            self,
            "Remove item",
            f"Remove {entry.item_type} {entry.item_identifier!r} from the collection?",
            confirm_label="Remove",
            cancel_label="Cancel",
            destructive=True,
            default_to_confirm=False,
        )
        if outcome.result is not ConfirmResult.CONFIRMED:
            return
        try:
            self._service.remove_item(
                self._current_collection_key, entry.identifier
            )
        except CollectionError as exc:
            self._show_error(str(exc))
            return
        self._reload_items()

    def _on_move_item_up(self) -> None:
        self._move_item(-1)

    def _on_move_item_down(self) -> None:
        self._move_item(1)

    def _move_item(self, delta: int) -> None:
        if self._service is None or self._current_collection_key is None:
            return
        row = self._items_list.currentRow()
        if row < 0:
            return
        new_row = row + delta
        if new_row < 0 or new_row >= self._items_list.count():
            return
        # Build the new order by swapping the two rows.
        ordered: list[CollectionItemView] = []
        for index in range(self._items_list.count()):
            entry = self._items_list.item(index).data(Qt.ItemDataRole.UserRole)
            if entry is not None:
                ordered.append(entry)
        ordered[row], ordered[new_row] = ordered[new_row], ordered[row]
        try:
            self._service.reorder_items(
                self._current_collection_key,
                [entry.identifier for entry in ordered],
            )
        except CollectionError as exc:
            self._show_error(str(exc))
            return
        self._reload_items()
        self._items_list.setCurrentRow(new_row)

    def _on_item_selected(
        self,
        current: QListWidgetItem | None,
        _previous: QListWidgetItem | None,
    ) -> None:
        enabled = current is not None
        self._edit_item_button.setEnabled(enabled)
        self._remove_item_button.setEnabled(enabled)
        if not enabled:
            self._move_up_button.setEnabled(False)
            self._move_down_button.setEnabled(False)
            return
        row = self._items_list.currentRow()
        self._move_up_button.setEnabled(row > 0)
        self._move_down_button.setEnabled(row < self._items_list.count() - 1)

    def _on_save_filter(self) -> None:
        if self._service is None or self._current_collection_key is None:
            return
        payload = self._filter_editor.toPlainText().strip()
        if not payload:
            self._show_error("Filter payload must not be empty.")
            return
        try:
            json.loads(payload)
        except ValueError as exc:
            self._show_error(f"Filter payload is not valid JSON: {exc}")
            return
        try:
            self._service.update_collection(
                self._current_collection_key,
                filter_json=payload,
            )
        except CollectionValidationError as exc:
            self._show_error("; ".join(exc.issues))
            return
        except CollectionError as exc:
            self._show_error(str(exc))
            return
        self.refresh()
        self._select_by_key(self._current_collection_key)

    # ------------------------------------------------------------------
    # Rendering helpers
    # ------------------------------------------------------------------
    def _show_detail(self, collection: CollectionView) -> None:
        self._current_collection_key = collection.key
        self._detail_title.setText(collection.display_label)
        self._detail_description.setText(collection.description or "")
        parts: list[str] = [f"Kind: {collection.kind.display_name}"]
        if collection.project_key:
            parts.append(f"Project: {collection.project_key}")
        parts.append(f"{collection.item_count} item(s)")
        self._detail_summary.setText(" · ".join(parts))
        self._edit_button.setEnabled(not collection.is_project_linked)
        is_smart = collection.kind is CollectionKind.SMART
        can_manage_items = collection.kind.allows_manual_items and not is_smart
        self._add_item_button.setEnabled(can_manage_items)
        if is_smart:
            self._items_hint.setText(
                "This collection is smart: its items are computed from "
                "the filter on the Filter tab. Edit the filter to change "
                "the set of items."
            )
            self._items_hint.show()
        else:
            self._items_hint.setText("")
            self._items_hint.hide()
        filter_enabled = collection.kind in {
            CollectionKind.SMART,
            CollectionKind.SAVED_SEARCH,
        }
        self._filter_editor.setEnabled(filter_enabled)
        self._save_filter_button.setEnabled(filter_enabled)
        if filter_enabled:
            payload = ""
            try:
                repo = self._service._repositories.get("collection")  # noqa: SLF001
                row = repo.find_by_key(collection.key)
                if row is not None and row.filter_json:
                    payload = row.filter_json
            except Exception:  # noqa: BLE001 - boundary
                payload = ""
            self._filter_editor.setPlainText(payload)
        else:
            self._filter_editor.setPlainText("")
        self._reload_items()
        if is_smart:
            self._detail_tabs.setCurrentWidget(self._filter_tab)

    def _clear_detail(self) -> None:
        self._current_collection_key = None
        self._detail_title.setText("Select a collection to view details.")
        self._detail_description.setText("")
        self._detail_summary.setText("")
        self._edit_button.setEnabled(False)
        self._add_item_button.setEnabled(False)
        self._items_hint.setText("")
        self._items_hint.hide()
        self._filter_editor.setPlainText("")
        self._filter_editor.setEnabled(False)
        self._save_filter_button.setEnabled(False)
        self._items_list.clear()
        self._edit_item_button.setEnabled(False)
        self._remove_item_button.setEnabled(False)
        self._move_up_button.setEnabled(False)
        self._move_down_button.setEnabled(False)

    def _reload_items(self) -> None:
        self._items_list.clear()
        if self._service is None or self._current_collection_key is None:
            return
        try:
            items = self._service.list_items(self._current_collection_key)
        except CollectionError as exc:
            _logger.warning("Unable to load collection items: %s", exc)
            return
        for item in items:
            label = f"{item.item_type}: {item.item_identifier}"
            if item.note:
                label += f"  —  {item.note[:60]}"
            entry = QListWidgetItem(label)
            entry.setData(Qt.ItemDataRole.UserRole, item)
            self._items_list.addItem(entry)
        if self._service is not None and self._current_collection_key:
            try:
                collection = self._service.get_collection(
                    self._current_collection_key
                )
                if collection.kind is CollectionKind.SMART:
                    self._edit_item_button.setEnabled(False)
                    self._remove_item_button.setEnabled(False)
                    self._move_up_button.setEnabled(False)
                    self._move_down_button.setEnabled(False)
            except Exception:  # noqa: BLE001 - boundary
                pass

    def _select_by_key(self, key: str) -> None:
        for row in range(self._model.rowCount()):
            collection = self._model.collection_at(row)
            if collection is None or collection.key != key:
                continue
            source_index = self._model.index(row, 0)
            proxy_index = self._proxy.mapFromSource(source_index)
            if proxy_index.isValid():
                self._table.setCurrentIndex(proxy_index)
                self._table.scrollTo(proxy_index)
                self._show_detail(collection)
            return

    def _update_summary(self, count: int) -> None:
        self.set_subtitle(
            f"{count} collection(s)." if count else "No collections yet."
        )

    def _update_empty_state(self) -> None:
        if self._model.rowCount() == 0:
            self.show_empty_state()
        else:
            self.show_content()

    def _show_error(self, message: str) -> None:
        DialogFactory.message(
            self,
            "Collection error",
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
def _display_value(collection: CollectionView, column: str) -> str:
    if column == "title":
        return collection.display_label
    if column == "kind":
        return collection.kind.display_name
    if column == "items":
        return str(collection.item_count)
    if column == "project":
        return collection.project_key or "—"
    if column == "updated_at":
        return (
            collection.updated_at[:19].replace("T", " ")
            if collection.updated_at
            else "—"
        )
    return ""


def _tooltip_value(collection: CollectionView, column: str) -> str:
    if column == "title":
        return collection.description or collection.key
    return ""


# ----------------------------------------------------------------------
# Form validators
# ----------------------------------------------------------------------
def _validate_collection_key(value: str) -> str | None:
    cleaned = value.strip()
    if not cleaned:
        return "Collection key must not be empty"
    if not cleaned[0].isalnum():
        return "Collection key must start with a letter or digit"
    for character in cleaned:
        if not (character.isalnum() or character in "-_"):
            return "Collection key may contain letters, digits, hyphens, and underscores"
    if cleaned != cleaned.lower():
        return "Collection key must be lowercase"
    return None


def _validate_optional_length(limit: int):
    def _validator(value: str) -> str | None:
        if len(value) > limit:
            return f"Must be at most {limit} characters"
        return None

    return _validator


def _validate_required(field: str):
    def _validator(value: str) -> str | None:
        if not value.strip():
            return f"{field} must not be empty"
        return None

    return _validator