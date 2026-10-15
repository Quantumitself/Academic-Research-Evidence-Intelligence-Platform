"""Modal dialog for linking a document to a collection or project.

The dialog presents two tabs: one for collections and one for projects.
Each tab lists the available targets with a checkbox indicating whether
the document is currently linked. Applying the dialog links or unlinks
the document based on the difference between the initial state and the
user's selection.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from academic_platform.application.document_linking.errors import (
    LinkingError,
    LinkingTargetNotFoundError,
)
from academic_platform.application.document_linking.model import (
    DocumentLinkView,
    LinkTarget,
)
from academic_platform.application.document_linking.service import (
    DocumentLinkingService,
)
from academic_platform.ui.dialogs.dialog_factory import DialogFactory
from academic_platform.ui.dialogs.message_dialog import MessageKind

_logger = logging.getLogger(__name__)


class LinkDocumentDialog(QDialog):
    """Modal dialog for linking a document to collections and projects."""

    links_changed = Signal(str)

    def __init__(
        self,
        service: DocumentLinkingService,
        document_key: str,
        *,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._service = service
        self._document_key = document_key
        self._initial_view: DocumentLinkView | None = None
        self._collection_checkboxes: dict[str, QCheckBox] = {}
        self._project_checkboxes: dict[str, QCheckBox] = {}

        self.setObjectName("linkDocumentDialog")
        self.setWindowTitle("Link to collection or project")
        self.setModal(True)
        self.setMinimumSize(560, 480)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)

        heading = QLabel(
            "Choose the collections and projects this document belongs to.",
            self,
        )
        heading.setObjectName("linkDialogHeading")
        heading.setWordWrap(True)
        layout.addWidget(heading)

        self._tabs = QTabWidget(self)
        self._tabs.setObjectName("linkDialogTabs")

        self._collections_tab = self._build_tab(
            "No collections are available.",
            self._collection_checkboxes,
        )
        self._projects_tab = self._build_tab(
            "No projects are available.",
            self._project_checkboxes,
        )
        self._tabs.addTab(self._collections_tab, "Collections")
        self._tabs.addTab(self._projects_tab, "Projects")
        layout.addWidget(self._tabs, 1)

        button_box = QDialogButtonBox(self)
        button_box.setObjectName("linkDialogButtonBox")
        self._apply_button = button_box.addButton(
            "Apply", QDialogButtonBox.ButtonRole.AcceptRole
        )
        self._cancel_button = button_box.addButton(
            "Cancel", QDialogButtonBox.ButtonRole.RejectRole
        )
        self._apply_button.setObjectName("linkDialogApply")
        self._cancel_button.setObjectName("linkDialogCancel")
        button_box.accepted.connect(self._on_apply)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        self._load()

    # ------------------------------------------------------------------
    # Construction helpers
    # ------------------------------------------------------------------
    def _build_tab(
        self,
        empty_message: str,
        checkbox_registry: dict[str, QCheckBox],
    ) -> QWidget:
        page = QWidget(self)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        scroll = QScrollArea(page)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        container = QWidget(scroll)
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(4)
        scroll.setWidget(container)

        layout.addWidget(scroll, 1)

        empty_label = QLabel(empty_message, page)
        empty_label.setObjectName("linkDialogEmpty")
        empty_label.setWordWrap(True)
        layout.addWidget(empty_label)

        # Store the parts on the page so the loader can access them.
        page._scroll = scroll              # type: ignore[attr-defined]
        page._container = container        # type: ignore[attr-defined]
        page._container_layout = container_layout  # type: ignore[attr-defined]
        page._empty_label = empty_label    # type: ignore[attr-defined]
        page._checkbox_registry = checkbox_registry  # type: ignore[attr-defined]
        return page

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------
    def _load(self) -> None:
        try:
            view = self._service.links_for_document(self._document_key)
        except LinkingError as exc:
            self._show_error("Unable to load links", str(exc))
            view = DocumentLinkView(document_key=self._document_key)
        self._initial_view = view
        self._populate_collections(view)
        self._populate_projects(view)

    def _populate_collections(self, view: DocumentLinkView) -> None:
        options = []
        try:
            options = self._service.list_collection_options()
        except LinkingError as exc:
            _logger.warning("Unable to list collections: %s", exc)
        linked_keys = {option.key for option in view.collections}
        self._populate_checkbox_tab(
            self._collections_tab,
            [(option.key, option.display_label) for option in options],
            linked_keys,
        )

    def _populate_projects(self, view: DocumentLinkView) -> None:
        options = []
        try:
            options = self._service.list_project_options()
        except LinkingError as exc:
            _logger.warning("Unable to list projects: %s", exc)
        linked_keys = {option.key for option in view.projects}
        self._populate_checkbox_tab(
            self._projects_tab,
            [(option.key, option.display_label) for option in options],
            linked_keys,
        )

    def _populate_checkbox_tab(
        self,
        tab: QWidget,
        entries: list[tuple[str, str]],
        linked_keys: set[str],
    ) -> None:
        registry = tab._checkbox_registry  # type: ignore[attr-defined]
        layout = tab._container_layout     # type: ignore[attr-defined]
        empty_label = tab._empty_label     # type: ignore[attr-defined]

        # Clear previous entries.
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        registry.clear()

        if not entries:
            empty_label.setVisible(True)
            return
        empty_label.setVisible(False)

        for key, label in entries:
            checkbox = QCheckBox(label, tab._container)  # type: ignore[attr-defined]
            checkbox.setObjectName(f"linkDialogCheckbox_{key}")
            checkbox.setChecked(key in linked_keys)
            registry[key] = checkbox
            layout.addWidget(checkbox)
        layout.addStretch(1)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------
    def _on_apply(self) -> None:
        if self._initial_view is None:
            self.reject()
            return
        errors: list[str] = []

        initial_collections = {option.key for option in self._initial_view.collections}
        selected_collections = {
            key for key, checkbox in self._collection_checkboxes.items()
            if checkbox.isChecked()
        }
        for key in selected_collections - initial_collections:
            try:
                self._service.link_document_to_collection(
                    self._document_key, key
                )
            except LinkingError as exc:
                errors.append(f"Collection {key!r}: {exc}")
        for key in initial_collections - selected_collections:
            try:
                self._service.unlink_document_from_collection(
                    self._document_key, key
                )
            except LinkingTargetNotFoundError:
                # The collection was removed externally; nothing to do.
                continue
            except LinkingError as exc:
                errors.append(f"Collection {key!r}: {exc}")

        initial_projects = {option.key for option in self._initial_view.projects}
        selected_projects = {
            key for key, checkbox in self._project_checkboxes.items()
            if checkbox.isChecked()
        }
        for key in selected_projects - initial_projects:
            try:
                self._service.link_document_to_project(
                    self._document_key, key
                )
            except LinkingError as exc:
                errors.append(f"Project {key!r}: {exc}")
        for key in initial_projects - selected_projects:
            try:
                self._service.unlink_document_from_project(
                    self._document_key, key
                )
            except LinkingTargetNotFoundError:
                continue
            except LinkingError as exc:
                errors.append(f"Project {key!r}: {exc}")

        if errors:
            self._show_error(
                "Some links could not be updated",
                "\n".join(errors),
            )
            self._load()
            return

        self.links_changed.emit(self._document_key)
        self.accept()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _show_error(self, title: str, message: str) -> None:
        DialogFactory.message(self, title, message, kind=MessageKind.ERROR)