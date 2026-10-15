"""Tests for the saved searches panel."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from academic_platform.application.saved_searches.model import SavedSearch  # noqa: E402
from academic_platform.application.saved_searches.service import (  # noqa: E402
    SavedSearchService,
)
from academic_platform.infrastructure.database import Database  # noqa: E402
from academic_platform.infrastructure.database.base import Base  # noqa: E402
from academic_platform.infrastructure.repositories.factory import (  # noqa: E402
    _REPOSITORY_REGISTRY,
)
from academic_platform.infrastructure.repositories.manager import (  # noqa: E402
    RepositoryManager,
)
from academic_platform.ui.pages.search.saved_searches_panel import (  # noqa: E402
    SavedSearchesPanel,
)


@pytest.fixture(scope="module")
def app() -> QApplication:
    return QApplication.instance() or QApplication([])


class _ShimmedManager:
    def __init__(self, database: Database) -> None:
        self._database = database
        self._sessions: list = []

    def get(self, key: str):
        session = self._database._session_factory()  # noqa: SLF001
        self._sessions.append(session)
        return _REPOSITORY_REGISTRY[key](session)

    def register_all(self, mapping) -> None:
        return None

    def close_all(self) -> None:
        for session in self._sessions:
            try:
                session.commit()
            except Exception:  # noqa: BLE001
                session.rollback()
            finally:
                session.close()
        self._sessions.clear()


def test_empty_panel(app: QApplication) -> None:
    database = Database.in_memory()
    try:
        Base.metadata.create_all(database.engine)
        manager = _ShimmedManager(database)
        panel = SavedSearchesPanel(lambda: SavedSearchService(manager))  # type: ignore[arg-type]
        from PySide6.QtWidgets import QLabel

        empty = panel.findChild(QLabel, "savedSearchesEmpty")
        assert empty is not None
        assert empty.isVisibleTo(panel)
        manager.close_all()
    finally:
        database.dispose()


def test_panel_lists_saved_searches(app: QApplication) -> None:
    database = Database.in_memory()
    try:
        Base.metadata.create_all(database.engine)
        manager = _ShimmedManager(database)
        service = SavedSearchService(manager)  # type: ignore[arg-type]
        service.create(SavedSearch(key="a", name="Alpha", query_text="ml"))
        manager.close_all()
        panel = SavedSearchesPanel(lambda: SavedSearchService(manager))  # type: ignore[arg-type]
        from PySide6.QtWidgets import QLabel

        labels = panel.findChildren(QLabel, "savedSearchLabel")
        assert labels
        assert labels[0].text() == "Alpha"
        manager.close_all()
    finally:
        database.dispose()