"""Tests for the search worker."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QCoreApplication, QEventLoop, QTimer  # noqa: E402

from academic_platform.ui.pages.search.search_controller import (  # noqa: E402
    SearchResponse,
    SourceReport,
    SourceStatus,
)
from academic_platform.ui.pages.search.search_worker import (  # noqa: E402
    SearchWorker,
    SearchWorkerHandle,
)


@pytest.fixture(scope="module")
def app() -> QCoreApplication:
    return QCoreApplication.instance() or QCoreApplication([])


class _StubController:
    def __init__(self, *, local: SearchResponse, remote: SearchResponse) -> None:
        self._local = local
        self._remote = remote

    def search_local(self, query: str) -> SearchResponse:
        return self._local

    def search_remote(self, query: str) -> SearchResponse:
        return self._remote


def test_worker_emits_response(app: QCoreApplication) -> None:
    local = SearchResponse(query="x", entries=())
    remote = SearchResponse(
        query="x",
        entries=(),
        source_reports=(
            SourceReport(source_label="A", status=SourceStatus.OK),
        ),
    )
    controller = _StubController(local=local, remote=remote)
    worker = SearchWorker(controller, "x", "remote")
    received: list[SearchResponse] = []
    worker.completed.connect(lambda response: received.append(response))
    worker.run()
    assert len(received) == 1
    assert received[0].source_reports[0].source_label == "A"


def test_worker_handles_controller_exception(app: QCoreApplication) -> None:
    class _BoomController:
        def search_local(self, query: str) -> SearchResponse:
            raise RuntimeError("boom")

        def search_remote(self, query: str) -> SearchResponse:
            raise RuntimeError("boom")

    worker = SearchWorker(_BoomController(), "x", "remote")
    received: list[SearchResponse] = []
    worker.completed.connect(lambda response: received.append(response))
    worker.run()
    assert len(received) == 1
    assert received[0].source_reports[0].status is SourceStatus.FAILED


def test_handle_starts_and_stops(app: QCoreApplication) -> None:
    local = SearchResponse(query="x", entries=())
    remote = SearchResponse(query="x", entries=())
    controller = _StubController(local=local, remote=remote)
    handle = SearchWorkerHandle(controller, "x", "remote")
    received: list[SearchResponse] = []
    handle.worker.completed.connect(lambda response: received.append(response))

    loop = QEventLoop()
    handle.worker.completed.connect(loop.quit)
    QTimer.singleShot(2000, loop.quit)

    handle.start()
    loop.exec()
    handle.cleanup()

    assert len(received) == 1