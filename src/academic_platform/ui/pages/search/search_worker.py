"""Background worker for executing search controllers.

The worker executes a search controller on a ``QThread`` so that the UI
thread is never blocked by network activity. It is used by the global
search page for both local and remote searches.

Design decisions
----------------
- The worker is a ``QObject`` moved to a ``QThread``. It receives a
  controller instance and a scope at construction and emits the
  ``SearchResponse`` when the work completes.
- Errors raised by the controller are caught and reported as a
  ``SearchResponse`` with a single failed source report. The worker
  never propagates an exception to the Qt event loop.
- The worker is single-use: it executes one search and then quits its
  thread. The page constructs a fresh worker for each search.
- The controller's synchronous interface is unchanged. The worker is
  the only component that decides to run it in the background.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import QObject, QThread, Signal

from academic_platform.ui.pages.search.search_controller import (
    SearchController,
    SearchResponse,
    SourceReport,
    SourceStatus,
)

_logger = logging.getLogger(__name__)


class SearchWorker(QObject):
    """Execute a search controller on a background thread."""

    completed = Signal(object)  # SearchResponse

    def __init__(
        self,
        controller: SearchController,
        query: str,
        scope: str,
    ) -> None:
        super().__init__()
        self._controller = controller
        self._query = query
        self._scope = scope

    def run(self) -> None:
        """Execute the search and emit the result."""
        try:
            if self._scope == "local":
                response = self._controller.search_local(self._query)
            else:
                response = self._controller.search_remote(self._query)
        except Exception as exc:  # noqa: BLE001 - defensive boundary
            _logger.exception("Search worker encountered an unexpected error")
            response = SearchResponse(
                query=self._query,
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
        self.completed.emit(response)


class SearchWorkerHandle:
    """Owns a ``QThread`` running a ``SearchWorker``.

    The handle keeps references to the thread and the worker so that
    both survive until the search completes. It is discarded by the
    caller once the completion callback has been invoked.
    """

    def __init__(
        self,
        controller: SearchController,
        query: str,
        scope: str,
    ) -> None:
        self._thread = QThread()
        self._worker = SearchWorker(controller, query, scope)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)

    @property
    def worker(self) -> SearchWorker:
        return self._worker

    def start(self) -> None:
        self._thread.start()

    def cleanup(self) -> None:
        """Stop the thread and release resources."""
        try:
            self._thread.quit()
            self._thread.wait(5000)
        except Exception:  # noqa: BLE001 - defensive boundary
            _logger.exception("Failed to stop search worker thread")