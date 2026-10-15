"""Tests for the source management dialog.

The tests construct the dialog against an in-memory database and a real
``SearchSourceService``. They do not exercise the network.
"""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QPushButton  # noqa: E402

from academic_platform.application.search_sources.service import (  # noqa: E402
    SearchSourceService,
)
from academic_platform.application.search_sources.source_config import (  # noqa: E402
    SourceConfig,
)
from academic_platform.infrastructure.database import Database  # noqa: E402
from academic_platform.infrastructure.database.base import Base  # noqa: E402
from academic_platform.infrastructure.repositories.factory import (  # noqa: E402
    _REPOSITORY_REGISTRY,
)
from academic_platform.infrastructure.search_providers.registry import (  # noqa: E402
    ProviderRegistry,
)
from academic_platform.ui.pages.settings.sources_dialog import (  # noqa: E402
    SourcesDialog,
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
        repository_class = _REPOSITORY_REGISTRY[key]
        return repository_class(session)

    def close_all(self) -> None:
        for session in self._sessions:
            try:
                session.commit()
            except Exception:  # noqa: BLE001
                session.rollback()
            finally:
                session.close()
        self._sessions.clear()


@pytest.fixture()
def service() -> SearchSourceService:
    database = Database.in_memory()
    Base.metadata.create_all(database.engine)
    manager = _ShimmedManager(database)
    registry = ProviderRegistry()
    service = SearchSourceService(manager, registry)  # type: ignore[arg-type]
    yield service
    manager.close_all()
    database.dispose()


def test_dialog_lists_sources(app: QApplication, service: SearchSourceService) -> None:
    service.create(
        SourceConfig(
            key="crossref",
            provider_key="crossref",
            display_name="Crossref",
            source_type="builtin",
            base_url="https://api.crossref.org",
        )
    )
    dialog = SourcesDialog(service)
    assert dialog.objectName() == "sourcesDialog"
    dialog.close()


def test_dialog_empty_state(app: QApplication, service: SearchSourceService) -> None:
    dialog = SourcesDialog(service)
    from PySide6.QtWidgets import QLabel

    placeholders = dialog.findChildren(QLabel, "sourcesDialogPlaceholder")
    assert placeholders
    dialog.close()


def test_dialog_refresh_button(app: QApplication, service: SearchSourceService) -> None:
    dialog = SourcesDialog(service)
    button = dialog.findChild(QPushButton, "sourcesDialogRefresh")
    assert button is not None
    button.click()
    dialog.close()


def test_dialog_add_button_exists(app: QApplication, service: SearchSourceService) -> None:
    dialog = SourcesDialog(service)
    button = dialog.findChild(QPushButton, "sourcesDialogAdd")
    assert button is not None
    dialog.close()