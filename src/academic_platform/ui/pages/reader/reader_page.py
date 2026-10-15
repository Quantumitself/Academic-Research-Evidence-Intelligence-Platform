"""Document reader page.

The reader page renders a PDF one page at a time through the
application-layer ``DocumentReaderService``. It provides:

- Page navigation (first, previous, next, last, jump to page).
- A zoom control that selects the render DPI.
- A table of contents panel that jumps to outline entries.
- A reading progress indicator.
- Keyboard shortcuts for the common navigation actions.

The page is a ``BasePage`` subclass, so it participates in the shell's
lifecycle contract. It does not live in the primary navigation; the
shell navigates to the reader when the user opens a document and
returns to the previous destination when the reader is closed.

Design decisions
----------------
- The reader page owns a ``DocumentReaderService`` instance. The
  service is constructed by the shell and attached to the page.
- Page rendering is synchronous. Rendering a single page at a time is
  fast enough for the reader's interactive use; a background render
  pipeline is delivered in a later phase if needed.
- The page cache lives in the service, not in the page. The page
  requests a page by number and DPI; the service returns the rendered
  image.
- The outline panel is populated once when the document is opened. The
  outline does not change while the document is open.
- The page emits ``close_requested`` when the user dismisses the
  reader. The shell handles the signal by returning to the previous
  destination and releasing the document handle.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, Qt, Signal
from PySide6.QtGui import QImage, QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from academic_platform.application.document_reading.errors import (
    DocumentReadingError,
    DocumentReadingNotFoundError,
    DocumentReadingUnsupportedError,
)
from academic_platform.application.document_reading.model import (
    DocumentOutlineEntry,
    RenderedPage,
)
from academic_platform.application.document_reading.service import (
    DocumentReaderService,
)
from academic_platform.ui.components.empty_state import EmptyState
from academic_platform.ui.components.section_card import SectionCard
from academic_platform.ui.dialogs.message_dialog import MessageKind
from academic_platform.ui.dialogs.dialog_factory import DialogFactory
from academic_platform.ui.main_window_destinations import get_destination
from academic_platform.ui.pages.base_page import BasePage
from academic_platform.application.annotations.service import (
    AnnotationService,
)
from academic_platform.ui.pages.reader.annotation_panel import (
    AnnotationPanel,
)
from academic_platform.application.document_search.service import (
    DocumentSearchService,
)
from academic_platform.ui.pages.reader.search_panel import (
    DocumentSearchPanel,
)
from academic_platform.application.document_linking.service import (
    DocumentLinkingService,
)
from academic_platform.ui.dialogs.link_document_dialog import (
    LinkDocumentDialog,
)
from academic_platform.application.assistant_handoff.service import (
    AssistantHandoffService,
)
from academic_platform.ui.dialogs.assistant_handoff_dialog import (
    AssistantHandoffDialog,
)



_logger = logging.getLogger(__name__)

_DEFAULT_DPI = 96
_ZOOM_CHOICES: tuple[tuple[str, int], ...] = (
    ("50 %", 48),
    ("75 %", 72),
    ("100 %", 96),
    ("125 %", 120),
    ("150 %", 144),
    ("200 %", 192),
    ("300 %", 288),
)


class ReaderPage(BasePage):
    """Document reader page."""

    #: Emitted when the user requests to close the reader.
    close_requested = Signal()

    #: Emitted when the user changes the current page.
    page_changed = Signal(str, int)

    def __init__(self, parent: QWidget | None = None) -> None:
        destination = get_destination("library")
        super().__init__(
            title="Reader",
            subtitle="Render PDF pages and navigate the document.",
            parent=parent,
        )
        self.setObjectName("readerPage")

        self._service: DocumentReaderService | None = None
        self._document_key: str = ""
        self._page_count: int = 0
        self._current_page: int = 1
        self._current_dpi: int = _DEFAULT_DPI
        self._outline: tuple[DocumentOutlineEntry, ...] = ()
        self._annotation_service: AnnotationService | None = None
        self._search_service: DocumentSearchService | None = None
        self._linking_service: DocumentLinkingService | None = None
        self._handoff_service: AssistantHandoffService | None = None
        self._notification_service = None

        self._build_content()
        self._wire_header_actions()
        self._install_shortcuts()
        self._install_empty_state(
            EmptyState(
                title="No document is open",
                message=(
                    "Open a document from the library to read it here."
                ),
                glyph="\u2261",
                parent=self,
            )
        )
        self.show_empty_state()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def attach_service(self, service: DocumentReaderService) -> None:
        """Attach the application-layer reader service."""
        self._service = service

    def load_document(self, document_key: str) -> bool:
        """Open the document and render its first page.

        Returns True when the document was opened successfully. On
        failure, the page remains in its empty state and the error is
        reported to the user.
        """
        if self._service is None:
            self._show_error(
                "Reader unavailable",
                "The reader service is not attached.",
            )
            return False
        # Close any previously open document before opening a new one.
        if self._document_key:
            try:
                self._service.close_document(self._document_key)
            except Exception:  # noqa: BLE001 - boundary
                _logger.exception(
                    "Unable to close the previous document %s",
                    self._document_key,
                )
            self._document_key = ""
        try:
            page_count, outline = self._service.open_document(document_key)
        except DocumentReadingNotFoundError as exc:
            self._show_error("Document not found", str(exc))
            return False
        except DocumentReadingUnsupportedError as exc:
            self._show_error("Document cannot be read", str(exc))
            return False
        except DocumentReadingError as exc:
            self._show_error("Unable to open document", str(exc))
            return False

        self._document_key = document_key
        self._page_count = page_count
        self._outline = outline
        self._current_page = 1
        self._populate_outline(outline)
        self._update_navigation_state()
        self._render_current_page()
        self.set_subtitle(f"{page_count} page(s).")
        self.show_content()
        if self._annotation_service is not None:
            self._annotation_panel.set_document(
                self._document_key, self._current_page
            )
        if self._search_service is not None:
            self._search_panel.set_document(self._document_key)
        if self._linking_service is not None:
            self._link_button.setEnabled(True)
        if self._handoff_service is not None:
            self._handoff_button.setEnabled(True)
        return True

    def close_document(self) -> None:
        """Release the current document and return to the empty state."""
        if self._service is not None and self._document_key:
            try:
                self._service.close_document(self._document_key)
            except Exception:  # noqa: BLE001 - boundary
                _logger.exception(
                    "Unable to close document %s", self._document_key
                )
        self._document_key = ""
        self._page_count = 0
        self._current_page = 1
        self._outline = ()
        self._page_view.clear()
        self._outline_list.clear()
        self.set_subtitle("Render PDF pages and navigate the document.")
        self.show_empty_state()
        self._annotation_panel.set_document("", 1)
        self._search_panel.set_document("")
        self._link_button.setEnabled(False)
        self._handoff_button.setEnabled(False)

    # ------------------------------------------------------------------
    # Content construction
    # ------------------------------------------------------------------
    def _build_content(self) -> None:
        content = QWidget(self)
        content.setObjectName("readerContent")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        layout.addWidget(self._build_navigation_bar(content))

        self._search_panel = DocumentSearchPanel(parent=content)
        self._search_panel.match_activated.connect(self._on_search_match_activated)
        self._search_panel.search_cleared.connect(self._on_search_cleared)
        layout.addWidget(self._search_panel)

        splitter = QSplitter(Qt.Orientation.Horizontal, content)
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(self._build_outline_panel(content))
        splitter.addWidget(self._build_page_view(content))
        self._annotation_panel = AnnotationPanel(parent=content)
        self._annotation_panel.annotation_selected.connect(
            self._on_annotation_selected
        )
        splitter.addWidget(self._annotation_panel)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)
        splitter.setSizes([220, 640, 320])
        layout.addWidget(splitter, 1)

        self._install_content(content, scrollable=False)

    def _build_navigation_bar(self, parent: QWidget) -> QWidget:
        container = QFrame(parent)
        container.setObjectName("readerNavigationBar")
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self._first_button = QPushButton("First", container)
        self._first_button.setObjectName("readerFirstButton")
        self._first_button.setAutoDefault(False)
        self._first_button.clicked.connect(self._on_first_page)
        layout.addWidget(self._first_button)

        self._previous_button = QPushButton("Previous", container)
        self._previous_button.setObjectName("readerPreviousButton")
        self._previous_button.setAutoDefault(False)
        self._previous_button.clicked.connect(self._on_previous_page)
        layout.addWidget(self._previous_button)

        self._page_spin = QSpinBox(container)
        self._page_spin.setObjectName("readerPageSpin")
        self._page_spin.setMinimum(1)
        self._page_spin.setMaximum(1)
        self._page_spin.setValue(1)
        self._page_spin.valueChanged.connect(self._on_page_spin_changed)
        layout.addWidget(self._page_spin)

        self._page_label = QLabel("of 0", container)
        self._page_label.setObjectName("readerPageLabel")
        layout.addWidget(self._page_label)

        self._next_button = QPushButton("Next", container)
        self._next_button.setObjectName("readerNextButton")
        self._next_button.setAutoDefault(False)
        self._next_button.clicked.connect(self._on_next_page)
        layout.addWidget(self._next_button)

        self._last_button = QPushButton("Last", container)
        self._last_button.setObjectName("readerLastButton")
        self._last_button.setAutoDefault(False)
        self._last_button.clicked.connect(self._on_last_page)
        layout.addWidget(self._last_button)

        layout.addStretch(1)

        zoom_label = QLabel("Zoom", container)
        zoom_label.setObjectName("readerZoomLabel")
        layout.addWidget(zoom_label)

        self._zoom_combo = QComboBox(container)
        self._zoom_combo.setObjectName("readerZoomCombo")
        for label, dpi in _ZOOM_CHOICES:
            self._zoom_combo.addItem(label, dpi)
        for index in range(self._zoom_combo.count()):
            if self._zoom_combo.itemData(index) == self._current_dpi:
                self._zoom_combo.setCurrentIndex(index)
                break
        self._zoom_combo.currentIndexChanged.connect(self._on_zoom_changed)
        layout.addWidget(self._zoom_combo)

        self._close_button = QPushButton("Close reader", container)
        self._close_button.setObjectName("readerCloseButton")
        self._close_button.setAutoDefault(False)
        self._close_button.clicked.connect(self._on_close)
        layout.addWidget(self._close_button)

        return container

    def _build_outline_panel(self, parent: QWidget) -> QWidget:
        card = SectionCard("Contents", parent)
        body = QWidget(card)
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(4)

        self._outline_list = QListWidget(body)
        self._outline_list.setObjectName("readerOutlineList")
        self._outline_list.setAlternatingRowColors(False)
        self._outline_list.itemActivated.connect(self._on_outline_activated)
        self._outline_list.itemClicked.connect(self._on_outline_activated)
        body_layout.addWidget(self._outline_list)

        card.set_content_widget(body)
        return card

    def _build_page_view(self, parent: QWidget) -> QWidget:
        container = QWidget(parent)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        scroll = QScrollArea(container)
        scroll.setObjectName("readerPageScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        self._page_view = QLabel(scroll)
        self._page_view.setObjectName("readerPageView")
        self._page_view.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._page_view.setTextInteractionFlags(
            Qt.TextInteractionFlag.NoTextInteraction
        )
        self._page_view.setMinimumSize(1, 1)
        scroll.setWidget(self._page_view)

        layout.addWidget(scroll, 1)

        self._progress_bar = QProgressBar(container)
        self._progress_bar.setObjectName("readerProgressBar")
        self._progress_bar.setRange(0, 1)
        self._progress_bar.setValue(0)
        self._progress_bar.setTextVisible(False)
        layout.addWidget(self._progress_bar)

        return container

    def _wire_header_actions(self) -> None:
        self._handoff_button = QPushButton("Hand off to assistant", self)
        self._handoff_button.setObjectName("readerHandoffButton")
        self._handoff_button.setAutoDefault(False)
        self._handoff_button.setEnabled(False)
        self._handoff_button.clicked.connect(self._on_handoff)
        self.add_header_action(self._handoff_button)

        self._link_button = QPushButton("Link to…", self)
        self._link_button.setObjectName("readerLinkButton")
        self._link_button.setAutoDefault(False)
        self._link_button.setEnabled(False)
        self._link_button.clicked.connect(self._on_link_document)
        self.add_header_action(self._link_button)

        self._close_header_button = QPushButton("Close", self)
        self._close_header_button.setObjectName("readerHeaderClose")
        self._close_header_button.setAutoDefault(False)
        self._close_header_button.clicked.connect(self._on_close)
        self.add_header_action(self._close_header_button)


    def _install_shortcuts(self) -> None:
        shortcuts = (
            (QKeySequence(Qt.Key.Key_Home), self._on_first_page),
            (QKeySequence(Qt.Key.Key_End), self._on_last_page),
            (QKeySequence(Qt.Key.Key_PageUp), self._on_previous_page),
            (QKeySequence(Qt.Key.Key_PageDown), self._on_next_page),
            (QKeySequence(Qt.Key.Key_Left), self._on_previous_page),
            (QKeySequence(Qt.Key.Key_Right), self._on_next_page),
            (QKeySequence(Qt.Key.Key_Escape), self._on_close),
            (QKeySequence.StandardKey.Find, self._focus_search),
        )
        for sequence, handler in shortcuts:
            shortcut = QShortcut(sequence, self)
            shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            shortcut.activated.connect(handler)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------
    def _on_first_page(self) -> None:
        self._goto_page(1)

    def _on_previous_page(self) -> None:
        self._goto_page(self._current_page - 1)

    def _on_next_page(self) -> None:
        self._goto_page(self._current_page + 1)

    def _on_last_page(self) -> None:
        self._goto_page(self._page_count)

    def _on_page_spin_changed(self, value: int) -> None:
        if value != self._current_page:
            self._goto_page(value)

    def _on_zoom_changed(self, _index: int) -> None:
        data = self._zoom_combo.currentData()
        try:
            dpi = int(data)
        except (TypeError, ValueError):
            return
        if dpi == self._current_dpi:
            return
        self._current_dpi = dpi
        self._render_current_page()

    def _on_outline_activated(self, item: QListWidgetItem) -> None:
        page_number = item.data(Qt.ItemDataRole.UserRole)
        try:
            page_number = int(page_number)
        except (TypeError, ValueError):
            return
        self._goto_page(page_number)

    def _on_close(self) -> None:
        self.close_document()
        self.close_requested.emit()

    def _focus_search(self) -> None:
        """Move keyboard focus to the in-document search input."""
        self._search_panel.focus_input()

    def _on_search_match_activated(self, match) -> None:
        """Jump to the page of an activated search match."""
        if match is None:
            return
        page_number = getattr(match, "page_number", None)
        if page_number:
            self._goto_page(page_number)

    def _on_search_cleared(self) -> None:
        """Handle the search panel's clear signal.

        The reader does not maintain a highlight overlay in this phase;
        the signal is honoured so that future overlays can clean up.
        """
        return

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------
    def _goto_page(self, page_number: int) -> None:
        if page_number < 1 or page_number > self._page_count:
            return
        if page_number == self._current_page:
            return
        self._current_page = page_number
        self._update_navigation_state()
        self._render_current_page()
        self.page_changed.emit(self._document_key, page_number)
        if self._annotation_service is not None:
            self._annotation_panel.set_current_page(page_number)

    def _render_current_page(self) -> None:
        if self._service is None or not self._document_key:
            return
        try:
            rendered = self._service.render_page(
                self._document_key,
                self._current_page,
                dpi=self._current_dpi,
            )
        except DocumentReadingError as exc:
            _logger.warning(
                "Unable to render page %d: %s", self._current_page, exc
            )
            self._page_view.setText(
                f"Unable to render page {self._current_page}."
            )
            self._page_view.setPixmap(QPixmap())
            return
        pixmap = _pixmap_from_bytes(rendered.image_bytes)
        if pixmap is None:
            self._page_view.setText("Unable to display the rendered page.")
            self._page_view.setPixmap(QPixmap())
            return
        self._page_view.setPixmap(pixmap)
        self._page_view.resize(pixmap.size())
        self._update_progress()

    def _update_navigation_state(self) -> None:
        self._page_spin.blockSignals(True)
        self._page_spin.setMaximum(max(1, self._page_count))
        self._page_spin.setValue(max(1, self._current_page))
        self._page_spin.blockSignals(False)
        self._page_label.setText(f"of {self._page_count}")
        self._first_button.setEnabled(self._current_page > 1)
        self._previous_button.setEnabled(self._current_page > 1)
        self._next_button.setEnabled(self._current_page < self._page_count)
        self._last_button.setEnabled(self._current_page < self._page_count)

    def _update_progress(self) -> None:
        total = max(1, self._page_count)
        self._progress_bar.setRange(0, total)
        self._progress_bar.setValue(min(self._current_page, total))

    def _populate_outline(
        self,
        outline: tuple[DocumentOutlineEntry, ...],
    ) -> None:
        self._outline_list.clear()
        if not outline:
            placeholder = QListWidgetItem("No table of contents available.")
            placeholder.setFlags(Qt.ItemFlag.NoItemFlags)
            self._outline_list.addItem(placeholder)
            return
        for entry in outline:
            item = QListWidgetItem(
                ("  " * max(0, entry.level - 1)) + entry.title
            )
            item.setData(Qt.ItemDataRole.UserRole, entry.page_number)
            self._outline_list.addItem(item)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def on_activated(self) -> None:
        if self._document_key:
            self._render_current_page()

    def on_deactivated(self) -> None:
        # The reader keeps the document open while the user navigates
        # elsewhere; the shell returns to the reader when the user
        # selects it again. Releasing the document happens when the
        # user closes the reader explicitly.
        pass

    def _show_error(self, title: str, message: str) -> None:
        DialogFactory.message(self, title, message, kind=MessageKind.ERROR)

    def attach_annotation_service(
        self,
        service: AnnotationService,
        notification_service=None,
    ) -> None:
        """Attach the annotation service and, optionally, the notification service."""
        self._annotation_service = service
        self._notification_service = notification_service
        if self._notification_service is not None:
            self._annotation_panel._notification_service = (  # noqa: SLF001
                self._notification_service
            )
        self._annotation_panel.attach_service(service)
        if self._document_key:
            self._annotation_panel.set_document(
                self._document_key, self._current_page
            )

    def _on_annotation_selected(self, _annotation_id: int, page_number: int) -> None:
        self._goto_page(page_number)

    def attach_search_service(self, service: DocumentSearchService) -> None:
        """Attach the in-document search service."""
        self._search_service = service
        self._search_panel.attach_service(service)
        if self._document_key:
            self._search_panel.set_document(self._document_key)

    def attach_linking_service(self, service: DocumentLinkingService) -> None:
        """Attach the document linking service."""
        self._linking_service = service

    def _on_link_document(self) -> None:
        if not self._document_key or self._linking_service is None:
            return
        dialog = LinkDocumentDialog(
            self._linking_service,
            self._document_key,
            parent=self,
        )
        dialog.exec()

    def attach_handoff_service(self, service: AssistantHandoffService) -> None:
        """Attach the reader → assistant handoff service."""
        self._handoff_service = service

    def _on_handoff(self) -> None:
        if not self._document_key or self._handoff_service is None:
            return
        dialog = AssistantHandoffDialog(
            self._handoff_service,
            self._document_key,
            current_page=self._current_page,
            parent=self,
        )
        dialog.exec()

# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
def _pixmap_from_bytes(image_bytes: bytes) -> QPixmap | None:
    if not image_bytes:
        return None
    buffer = QBuffer()
    buffer.setData(QByteArray(image_bytes))
    buffer.open(QIODevice.OpenModeFlag.ReadOnly)
    image = QImage()
    if not image.loadFromData(buffer.data(), "PNG"):
        buffer.close()
        return None
    buffer.close()
    return QPixmap.fromImage(image)

