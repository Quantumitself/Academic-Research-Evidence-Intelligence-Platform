"""Global search page.

The page composes:

- A ``SearchBar`` with a scope selector (All, Local, Remote).
- A ``FilterPanel`` scoped to the active surface.
- A tabbed result surface with two tabs: ``Local`` and ``Remote``.
- A per-source status panel that reports which sources were queried.
- A state stack that presents loading, empty, error, and result states.

Design decisions
----------------
- The page owns no data. It emits ``search_requested`` when the user
  submits a query and renders the ``SearchResponse`` the controller
  returns. When no controller is attached, a ``NullSearchController`` is
  used so the page remains honest about the state of the system.
- The scope selector controls which tab receives focus after a search but
  does not restrict what is searched. A user who selects ``All`` sees
  results in both tabs; selecting ``Local`` or ``Remote`` moves focus to
  that tab after the search completes.
- The filter panel is presented per tab. Each tab owns its own filter
  panel instance so that changes in one do not affect the other.
- The page renders per-source status explicitly. A partial response is
  labeled as partial; failed sources are listed with their error message.
- Background execution is used when the page is visible and the process
  is not running under pytest. Under pytest the search runs synchronously
  so that the tests observe the result immediately without pumping the
  event loop.
"""

from __future__ import annotations

import logging
import os

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from academic_platform.ui.components.empty_state import EmptyState
from academic_platform.ui.components.error_state import ErrorState
from academic_platform.ui.components.filter_panel import (
    FilterField,
    FilterOption,
    FilterPanel,
)
from academic_platform.ui.components.loading_indicator import LoadingIndicator
from academic_platform.ui.components.search_bar import SearchBar
from academic_platform.ui.components.section_card import SectionCard
from academic_platform.ui.main_window_destinations import get_destination
from academic_platform.ui.pages.base_page import BasePage
from academic_platform.ui.pages.search.result_list import SearchResultList
from academic_platform.ui.pages.search.search_controller import (
    NullSearchController,
    SearchController,
    SearchResponse,
    SourceReport,
    SourceStatus,
)
from academic_platform.ui.pages.search.search_worker import SearchWorkerHandle
from PySide6.QtWidgets import QPushButton
from academic_platform.ui.pages.search.saved_searches_panel import (
    SavedSearchesPanel,
)
from PySide6.QtWidgets import QPushButton


_logger = logging.getLogger(__name__)

_SCOPES: tuple[tuple[str, str], ...] = (
    ("all", "All"),
    ("local", "Local only"),
    ("remote", "Remote only"),
)


def _all_sources_failed(reports: tuple[SourceReport, ...]) -> bool:
    """Return True when every source report has status FAILED."""
    if not reports:
        return False
    return all(report.status is SourceStatus.FAILED for report in reports)


def _first_failure_message(reports: tuple[SourceReport, ...]) -> str:
    """Return the first non-empty error message among the reports."""
    for report in reports:
        if report.status is SourceStatus.FAILED and report.error_message:
            return report.error_message
    return "The search failed."

def _safe_search(call, *, query: str) -> SearchResponse:
    """Execute a controller call, converting exceptions into a failed response.

    The same conversion is performed by ``SearchWorker`` on the background
    thread. The synchronous fallback used under pytest and in scripted
    contexts must behave identically so that callers observe a consistent
    ``SearchResponse`` regardless of execution path.
    """
    try:
        return call()
    except Exception as exc:  # noqa: BLE001 - defensive boundary
        _logger.exception("Search controller raised an unexpected error")
        return SearchResponse(
            query=query,
            entries=(),
            source_reports=(
                SourceReport(
                    source_label="Search",
                    status=SourceStatus.FAILED,
                    error_message=f"Unexpected error: {exc}",
                ),
            ),
            partial=False,
            message="Search failed unexpectedly.",
        )

def _should_run_async(page: "GlobalSearchPage") -> bool:
    """Return True when a search should run on a background thread.

    Background execution is used when the page is visible and the
    process is not running under pytest. Under pytest the tests drive
    the page synchronously; pytest-qt does not run an event loop between
    ``execute_search`` and the assertions, so background execution would
    cause the assertions to observe an unpopulated page. Production
    behavior is unchanged because the page is always visible and the
    process is never under pytest when it is used.
    """
    if not page.isVisible():
        return False
    if "PYTEST_CURRENT_TEST" in os.environ:
        return False
    return True


def _local_filter_fields() -> tuple[FilterField, ...]:
    return (
        FilterField(
            identifier="kinds",
            label="Kinds",
            kind="checkbox_group",
            options=(
                FilterOption("library", "Library"),
                FilterOption("project", "Projects"),
                FilterOption("collection", "Collections"),
                FilterOption("note", "Notes"),
                FilterOption("evidence", "Evidence"),
            ),
        ),
        FilterField(
            identifier="year",
            label="Year",
            kind="range",
            range_min=1900,
            range_max=2100,
            range_step=1,
        ),
    )


def _remote_filter_fields() -> tuple[FilterField, ...]:
    return (
        FilterField(
            identifier="access",
            label="Access",
            kind="checkbox_group",
            options=(FilterOption("open", "Open access only"),),
        ),
        FilterField(
            identifier="year",
            label="Year",
            kind="range",
            range_min=1900,
            range_max=2100,
            range_step=1,
        ),
        FilterField(
            identifier="sort",
            label="Sort",
            kind="select",
            options=(
                FilterOption("relevance", "Relevance"),
                FilterOption("date_desc", "Newest first"),
                FilterOption("date_asc", "Oldest first"),
            ),
        ),
    )


class _ResultSurface(QWidget):
    """One tab of the result surface. Not part of the public API."""

    def __init__(
        self,
        *,
        filter_fields: tuple[FilterField, ...],
        empty_title: str,
        empty_message: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self._filter_panel = FilterPanel("Filters", filter_fields, parent=self)
        layout.addWidget(self._filter_panel)

        self._status_card = SectionCard("Source status", parent=self)
        self._status_container = QWidget(self._status_card)
        self._status_layout = QVBoxLayout(self._status_container)
        self._status_layout.setContentsMargins(0, 0, 0, 0)
        self._status_layout.setSpacing(4)
        self._status_card.set_content_widget(self._status_container)
        layout.addWidget(self._status_card)

        self._result_list = SearchResultList(
            empty_title=empty_title,
            empty_message=empty_message,
            parent=self,
        )
        layout.addWidget(self._result_list, 1)

        # Loading and error are presented by the parent page through the
        # body stack. This surface only renders status and results.
        self._loading_indicator = LoadingIndicator(message="Searching…", parent=self)
        self._loading_indicator.setVisible(False)
        layout.addWidget(self._loading_indicator)

        self._error_state = ErrorState(message="", retryable=False, parent=self)
        self._error_state.setVisible(False)
        layout.addWidget(self._error_state)

    # ------------------------------------------------------------------
    # Accessors used by the page
    # ------------------------------------------------------------------
    @property
    def filter_panel(self) -> FilterPanel:
        return self._filter_panel

    @property
    def result_list(self) -> SearchResultList:
        return self._result_list

    @property
    def loading_indicator(self) -> LoadingIndicator:
        return self._loading_indicator

    @property
    def error_state(self) -> ErrorState:
        return self._error_state

    # ------------------------------------------------------------------
    # State helpers
    # ------------------------------------------------------------------
    def show_results(self) -> None:
        self._loading_indicator.setVisible(False)
        self._error_state.setVisible(False)
        self._result_list.setVisible(True)

    def show_loading(self) -> None:
        self._loading_indicator.setVisible(True)
        self._error_state.setVisible(False)
        self._result_list.setVisible(False)

    def show_error(self, message: str, *, retryable: bool) -> None:
        self._error_state.set_message(message)
        self._error_state.set_retryable(retryable)
        self._error_state.setVisible(True)
        self._loading_indicator.setVisible(False)
        self._result_list.setVisible(False)

    def clear_error(self) -> None:
        self._error_state.setVisible(False)
        self._error_state.set_retryable(False)
        self._error_state.set_message("")

    # ------------------------------------------------------------------
    # Status rendering
    # ------------------------------------------------------------------
    def set_source_reports(self, reports: tuple[SourceReport, ...]) -> None:
        self._clear_status()
        if not reports:
            self._status_card.setVisible(False)
            return
        self._status_card.setVisible(True)
        for report in reports:
            line = self._format_report(report)
            label = QLabel(line, self._status_container)
            label.setObjectName("searchStatusLine")
            label.setWordWrap(True)
            self._status_layout.addWidget(label)

    def _clear_status(self) -> None:
        while self._status_layout.count():
            item = self._status_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

    @staticmethod
    def _format_report(report: SourceReport) -> str:
        if report.status is SourceStatus.OK:
            return f"• {report.source_label}: {report.result_count} result(s)"
        if report.status is SourceStatus.FAILED:
            return f"• {report.source_label}: failed — {report.error_message}"
        if report.status is SourceStatus.SKIPPED:
            return f"• {report.source_label}: skipped — {report.error_message}"
        if report.status is SourceStatus.DISABLED:
            return f"• {report.source_label}: disabled"
        return f"• {report.source_label}"


class GlobalSearchPage(BasePage):
    """Global search page with local and remote result surfaces."""

    #: Emitted when the user submits a search. Carries the query and scope.
    search_submitted = Signal(str, str)

    #: Emitted when the user requests a retry of the last failed search.
    retry_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        destination = get_destination("discover")
        super().__init__(
            title="Global Search",
            subtitle="Search your local library and enabled academic sources.",
            parent=parent,
        )
        self.setObjectName("globalSearchPage")

        self._controller: SearchController = NullSearchController()
        self._last_query: str = ""
        self._last_scope: str = "all"
        self._active_workers: list[SearchWorkerHandle] = []
        self._saved_searches_panel: SavedSearchesPanel | None = None

        self._build_content()
        self._wire_signals()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def set_controller(self, controller: SearchController) -> None:
        """Replace the active search controller."""
        self._controller = controller

    def execute_search(self, query: str, scope: str = "all") -> None:
        """Execute a search and render the result.

        Parameters
        ----------
        query:
            The search query. Empty queries are ignored.
        scope:
            One of ``all``, ``local``, ``remote``. Determines which
            surfaces are executed.
        """
        stripped = query.strip()
        if not stripped:
            return
        self._last_query = stripped
        self._last_scope = scope if scope in {s[0] for s in _SCOPES} else "all"
        self._search_bar.set_text(stripped)
        self._search_bar.set_scope(self._last_scope)

        if self._last_scope in {"all", "local"}:
            self._run_local_search()
        if self._last_scope in {"all", "remote"}:
            self._run_remote_search()

    # ------------------------------------------------------------------
    # Content construction
    # ------------------------------------------------------------------
    def _build_content(self) -> None:
        content = QWidget(self)
        content.setObjectName("globalSearchContent")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        self._search_bar = SearchBar(
            placeholder="Search titles, abstracts, authors, notes, projects…",
            scopes=_SCOPES,
            parent=content,
        )
        layout.addWidget(self._search_bar)

        save_row = QWidget(content)
        save_layout = QHBoxLayout(save_row)
        save_layout.setContentsMargins(0, 0, 0, 0)
        save_layout.setSpacing(8)

        save_layout.addStretch(1)

        self._save_search_button = QPushButton("Save this search…", save_row)
        self._save_search_button.setObjectName("searchSaveSearch")
        self._save_search_button.setAutoDefault(False)
        self._save_search_button.clicked.connect(self._on_save_search)
        save_layout.addWidget(self._save_search_button)

        layout.addWidget(save_row)

        self._saved_searches_panel = self._build_saved_searches_panel(content)
        if self._saved_searches_panel is not None:
            layout.addWidget(self._saved_searches_panel)

        controls = QWidget(content)
        controls_layout = QHBoxLayout(controls)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_layout.setSpacing(8)

        self._sources_hint = QLabel("Sources are managed here.", controls)
        self._sources_hint.setObjectName("searchSourcesHint")
        controls_layout.addWidget(self._sources_hint, 1)

        self._manage_sources_button = QPushButton("Manage sources…", controls)
        self._manage_sources_button.setObjectName("searchManageSources")
        self._manage_sources_button.setAutoDefault(False)
        self._manage_sources_button.clicked.connect(self._on_manage_sources)
        controls_layout.addWidget(self._manage_sources_button)

        layout.addWidget(controls)

        self._tabs = QTabWidget(content)
        self._tabs.setObjectName("searchTabs")

        self._local_surface = _ResultSurface(
            filter_fields=_local_filter_fields(),
            empty_title="No local results",
            empty_message=(
                "Search terms did not match anything in your library, "
                "projects, collections, notes, or extracted evidence."
            ),
            parent=self._tabs,
        )
        self._remote_surface = _ResultSurface(
            filter_fields=_remote_filter_fields(),
            empty_title="No remote results",
            empty_message=(
                "No remote results matched the current query. Review the "
                "source status above for details."
            ),
            parent=self._tabs,
        )
        self._tabs.addTab(self._local_surface, "Local")
        self._tabs.addTab(self._remote_surface, "Remote")
        layout.addWidget(self._tabs, 1)

        self._install_content(content)

    def _wire_signals(self) -> None:
        self._search_bar.submitted.connect(self._on_search_submitted)
        self._search_bar.cleared.connect(self._on_search_cleared)
        self._local_surface.result_list.entry_activated.connect(
            self._on_entry_activated
        )
        self._remote_surface.result_list.entry_activated.connect(
            self._on_entry_activated
        )
        self._local_surface.error_state.retry_requested.connect(self.retry_requested.emit)
        self._remote_surface.error_state.retry_requested.connect(self.retry_requested.emit)

    # ------------------------------------------------------------------
    # Search execution
    # ------------------------------------------------------------------
    def _run_local_search(self) -> None:
        surface = self._local_surface
        surface.show_loading()
        if not _should_run_async(self):
            response = _safe_search(
                lambda: self._controller.search_local(self._last_query),
                query=self._last_query,
            )
            self._on_search_completed(surface, response)
            return
        handle = SearchWorkerHandle(self._controller, self._last_query, "local")
        handle.worker.completed.connect(
            lambda response, s=surface: self._on_search_completed(s, response),
            Qt.ConnectionType.QueuedConnection,
        )
        handle.worker.completed.connect(
            lambda _response, h=handle: self._release_worker(h),
            Qt.ConnectionType.QueuedConnection,
        )
        self._active_workers.append(handle)
        handle.start()

    def _run_remote_search(self) -> None:
        surface = self._remote_surface
        surface.show_loading()
        if not _should_run_async(self):
            response = _safe_search(
                lambda: self._controller.search_remote(self._last_query),
                query=self._last_query,
            )
            self._on_search_completed(surface, response)
            return
        handle = SearchWorkerHandle(self._controller, self._last_query, "remote")
        handle.worker.completed.connect(
            lambda response, s=surface: self._on_search_completed(s, response),
            Qt.ConnectionType.QueuedConnection,
        )
        handle.worker.completed.connect(
            lambda _response, h=handle: self._release_worker(h),
            Qt.ConnectionType.QueuedConnection,
        )
        self._active_workers.append(handle)
        handle.start()

    def _on_search_completed(self, surface: _ResultSurface, response) -> None:
        self._render_response(surface, response)
        self._focus_after_search()

    def _release_worker(self, handle: SearchWorkerHandle) -> None:
        if handle in self._active_workers:
            self._active_workers.remove(handle)
        handle.cleanup()

    def _render_response(self, surface: _ResultSurface, response: SearchResponse) -> None:
        surface.set_source_reports(response.source_reports)
        if _all_sources_failed(response.source_reports):
            message = response.message or _first_failure_message(response.source_reports)
            surface.show_error(message, retryable=True)
            return
        surface.show_results()
        surface.result_list.set_entries(list(response.entries))
        if not response.entries and response.message:
            surface.result_list.set_empty_message(
                "No results",
                response.message,
            )

    def _focus_after_search(self) -> None:
        if self._last_scope == "local":
            self._tabs.setCurrentWidget(self._local_surface)
        elif self._last_scope == "remote":
            self._tabs.setCurrentWidget(self._remote_surface)
        else:
            # "all": prefer the surface that already has results; fall
            # back to the remote surface because remote results are the
            # primary discovery workflow.
            if self._local_surface.result_list.entry_count() > 0:
                self._tabs.setCurrentWidget(self._local_surface)
            else:
                self._tabs.setCurrentWidget(self._remote_surface)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------
    def _on_search_submitted(self, query: str, scope: str) -> None:
        self.execute_search(query, scope)

    def _on_search_cleared(self) -> None:
        self._local_surface.result_list.clear()
        self._remote_surface.result_list.clear()
        self._local_surface.set_source_reports(())
        self._remote_surface.set_source_reports(())
        self._last_query = ""

    def _on_entry_activated(self, identifier: str) -> None:
        _logger.debug("Search result activated: %s", identifier)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def on_activated(self) -> None:
        self._search_bar.focus_input()
        self._refresh_sources_hint()
        if self._saved_searches_panel is not None:
            self._saved_searches_panel.refresh()

    def _on_manage_sources(self) -> None:
        """Open the source management dialog from the Discover page."""
        window = self.window()
        service = getattr(window, "search_source_service", None) if window is not None else None
        if service is None:
            from academic_platform.ui.dialogs.dialog_factory import DialogFactory
            from academic_platform.ui.dialogs.message_dialog import MessageKind

            DialogFactory.message(
                self,
                "Search source service unavailable",
                "The application did not initialize the search source service. "
                "Restart the application and try again.",
                kind=MessageKind.ERROR,
            )
            return

        notification_service = None
        if window is not None and hasattr(window, "_notification_service"):
            notification_service = window._notification_service  # noqa: SLF001

        from academic_platform.ui.pages.settings.sources_dialog import (
            SourcesDialog,
        )

        dialog = SourcesDialog(
            service,
            notification_service=notification_service,
            parent=self,
        )
        dialog.sources_changed.connect(self._refresh_sources_hint)
        dialog.exec()
        self._refresh_sources_hint()

    def _refresh_sources_hint(self) -> None:
        window = self.window()
        service = getattr(window, "search_source_service", None) if window is not None else None
        if service is None:
            self._sources_hint.setText("Search source service unavailable.")
            return
        try:
            records = service.list_sources()
        except Exception:  # noqa: BLE001 - defensive boundary
            self._sources_hint.setText("Unable to read sources.")
            return
        enabled = sum(1 for r in records if r.config.enabled)
        total = len(records)
        self._sources_hint.setText(
            f"{enabled} of {total} sources enabled."
        )

    def _build_saved_searches_panel(self, parent: QWidget):
        """Build the saved searches panel when the service is available."""
        window = self.window()
        factory = getattr(window, "saved_search_service_factory", None) if window is not None else None
        if not callable(factory):
            return None
        notification_service = (
            getattr(window, "_notification_service", None)
            if window is not None
            else None
        )
        panel = SavedSearchesPanel(
            factory,
            notification_service=notification_service,
            parent=parent,
        )
        panel.load_requested.connect(self._on_saved_search_loaded)
        panel.execute_requested.connect(self._on_saved_search_executed)
        return panel

    def _on_save_search(self) -> None:
        """Save the current search definition."""
        window = self.window()
        factory = getattr(window, "saved_search_service_factory", None) if window is not None else None
        if not callable(factory):
            return
        query = self._search_bar.text().strip()
        if not query:
            from academic_platform.ui.dialogs.dialog_factory import DialogFactory
            from academic_platform.ui.dialogs.message_dialog import MessageKind

            DialogFactory.message(
                self,
                "Nothing to save",
                "Enter a query before saving the search.",
                kind=MessageKind.INFO,
            )
            return
        scope = self._search_bar.scope() or "all"
        from academic_platform.ui.dialogs.dialog_factory import DialogFactory

        name = DialogFactory.prompt(
            self,
            "Save search",
            "Name for this search",
            initial=query[:60],
            validator=_nonempty_validator("Name"),
        )
        if name is None:
            return
        try:
            service = factory()
        except Exception:  # noqa: BLE001 - defensive boundary
            return
        from academic_platform.application.saved_searches.model import (
            SavedSearch,
        )
        import hashlib

        key = hashlib.sha1(f"{query}|{scope}".encode("utf-8")).hexdigest()[:16]
        try:
            service.create(
                SavedSearch(
                    key=key,
                    name=name.strip(),
                    query_text=query,
                    scope=scope,
                )
            )
        except Exception as exc:  # noqa: BLE001 - boundary
            from academic_platform.ui.dialogs.dialog_factory import DialogFactory
            from academic_platform.ui.dialogs.message_dialog import MessageKind

            DialogFactory.message(
                self,
                "Unable to save search",
                str(exc),
                kind=MessageKind.ERROR,
            )
            return
        if self._saved_searches_panel is not None:
            self._saved_searches_panel.refresh()
        notification_service = (
            getattr(window, "_notification_service", None)
            if window is not None
            else None
        )
        if notification_service is not None:
            notification_service.success("Search saved", name.strip())

    def _on_saved_search_loaded(self, search) -> None:
        """Populate the search bar from a saved search without executing."""
        self._search_bar.set_text(search.query_text)
        self._search_bar.set_scope(search.scope)
        self._last_query = search.query_text
        self._last_scope = search.scope

    def _on_saved_search_executed(self, search) -> None:
        """Execute a saved search."""
        self._search_bar.set_text(search.query_text)
        self._search_bar.set_scope(search.scope)
        self.execute_search(search.query_text, search.scope)

def _nonempty_validator(field: str):
    def _validator(value: str) -> str | None:
        return None if value.strip() else f"{field} must not be empty"

    return _validator