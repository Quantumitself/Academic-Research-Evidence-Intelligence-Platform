"""In-document search panel for the reader.

The panel exposes a query input, a case-sensitivity toggle, a regular
expression toggle, and a list of matches. It emits signals when the
user activates a match so that the reader can jump to the page and
highlight the match.

Design decisions
----------------
- The panel is a self-contained widget. It reads through the
  application-layer ``DocumentSearchService``.
- The panel is told which document is current by the reader page.
- Match activation emits ``match_activated(match)``; the reader decides
  how to highlight the match on the rendered page.
- The panel never reads the database or the PDF directly.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from academic_platform.application.document_search.errors import (
    DocumentSearchError,
    DocumentSearchNotFoundError,
)
from academic_platform.application.document_search.model import (
    DocumentSearchMatch,
)
from academic_platform.application.document_search.service import (
    DocumentSearchService,
)
from academic_platform.ui.dialogs.dialog_factory import DialogFactory
from academic_platform.ui.dialogs.message_dialog import MessageKind

_logger = logging.getLogger(__name__)


class DocumentSearchPanel(QFrame):
    """In-document search panel."""

    #: Emitted when the user activates a match. Carries the match.
    match_activated = Signal(object)

    #: Emitted when the search is cleared. The reader uses this to
    #: remove any active highlight.
    search_cleared = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("documentSearchPanel")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self._service: DocumentSearchService | None = None
        self._document_key: str = ""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 12)
        layout.setSpacing(6)

        heading = QLabel("Find in document", self)
        heading.setObjectName("documentSearchHeading")
        layout.addWidget(heading)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)

        self._input = QLineEdit(self)
        self._input.setObjectName("documentSearchInput")
        self._input.setPlaceholderText("Search text…")
        self._input.returnPressed.connect(self._on_search)
        self._input.textChanged.connect(self._on_text_changed)
        row.addWidget(self._input, 1)

        self._search_button = QPushButton("Find", self)
        self._search_button.setObjectName("documentSearchButton")
        self._search_button.setAutoDefault(False)
        self._search_button.clicked.connect(self._on_search)
        row.addWidget(self._search_button)

        layout.addLayout(row)

        toggles = QHBoxLayout()
        toggles.setContentsMargins(0, 0, 0, 0)
        toggles.setSpacing(6)

        self._case_checkbox = QCheckBox("Case sensitive", self)
        self._case_checkbox.setObjectName("documentSearchCaseSensitive")
        self._case_checkbox.toggled.connect(self._on_search)
        toggles.addWidget(self._case_checkbox)

        self._regex_checkbox = QCheckBox("Regular expression", self)
        self._regex_checkbox.setObjectName("documentSearchRegex")
        self._regex_checkbox.toggled.connect(self._on_search)
        toggles.addWidget(self._regex_checkbox)

        toggles.addStretch(1)

        self._clear_button = QPushButton("Clear", self)
        self._clear_button.setObjectName("documentSearchClear")
        self._clear_button.setAutoDefault(False)
        self._clear_button.clicked.connect(self._on_clear)
        toggles.addWidget(self._clear_button)

        layout.addLayout(toggles)

        self._summary_label = QLabel("No search has been run.", self)
        self._summary_label.setObjectName("documentSearchSummary")
        self._summary_label.setWordWrap(True)
        layout.addWidget(self._summary_label)

        self._list = QListWidget(self)
        self._list.setObjectName("documentSearchResults")
        self._list.setAlternatingRowColors(False)
        self._list.itemActivated.connect(self._on_item_activated)
        self._list.itemClicked.connect(self._on_item_activated)
        layout.addWidget(self._list, 1)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def attach_service(self, service: DocumentSearchService) -> None:
        self._service = service
        self._clear_results()

    def set_document(self, document_key: str) -> None:
        self._document_key = document_key
        self._on_clear()

    def focus_input(self) -> None:
        self._input.setFocus(Qt.FocusReason.ShortcutFocusReason)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------
    def _on_text_changed(self, _text: str) -> None:
        # Clearing the input clears the results so the reader's active
        # highlight is removed.
        if not self._input.text().strip():
            self._clear_results()

    def _on_search(self) -> None:
        query = self._input.text().strip()
        if not query:
            self._clear_results()
            return
        if self._service is None or not self._document_key:
            self._summary_label.setText("No document is open.")
            return
        try:
            result = self._service.search(
                self._document_key,
                query,
                case_sensitive=self._case_checkbox.isChecked(),
                use_regex=self._regex_checkbox.isChecked(),
            )
        except DocumentSearchNotFoundError as exc:
            self._summary_label.setText(str(exc))
            return
        except DocumentSearchError as exc:
            self._show_error("Search failed", str(exc))
            return
        self._render_result(result)

    def _on_clear(self) -> None:
        self._input.clear()
        self._clear_results()

    def _on_item_activated(self, item: QListWidgetItem) -> None:
        match = item.data(Qt.ItemDataRole.UserRole)
        if match is None:
            return
        self.match_activated.emit(match)

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------
    def _render_result(self, result) -> None:
        self._list.clear()
        if result.match_count == 0:
            self._summary_label.setText("No matches found.")
            return
        self._summary_label.setText(
            f"{result.match_count} match(es) across "
            f"{len(result.pages_with_matches)} page(s)."
            + (f" {result.message}" if result.message else "")
        )
        for match in result.matches:
            item = QListWidgetItem(_format_match_label(match))
            item.setData(Qt.ItemDataRole.UserRole, match)
            item.setToolTip(match.snippet.replace("[[", "").replace("]]", ""))
            self._list.addItem(item)

    def _clear_results(self) -> None:
        self._list.clear()
        self._summary_label.setText("No search has been run.")
        self.search_cleared.emit()

    def _show_error(self, title: str, message: str) -> None:
        DialogFactory.message(self, title, message, kind=MessageKind.ERROR)


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
def _format_match_label(match: DocumentSearchMatch) -> str:
    page = match.page_number if match.page_number is not None else "?"
    snippet = match.snippet
    # The snippet already carries markers; strip them for the label and
    # render the matched text with quotes.
    plain = snippet.replace("[[", "").replace("]]", "")
    return f"Page {page}: {plain}"


def match_display_text(match: DocumentSearchMatch) -> str:
    """Return the match's snippet with its highlight markers removed."""
    return match.snippet.replace("[[", "").replace("]]", "")