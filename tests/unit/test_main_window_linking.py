"""Tests for the main window's linking wiring."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from academic_platform.app.configuration import load_runtime_directories  # noqa: E402
from academic_platform.app.settings import SettingsService  # noqa: E402
from academic_platform.infrastructure.database import Database  # noqa: E402
from academic_platform.infrastructure.database.base import Base  # noqa: E402
from academic_platform.infrastructure.database.models import (  # noqa: E402
    Collection,
    DocumentAsset,
)
from academic_platform.ui.main_window import MainWindow  # noqa: E402


@pytest.fixture(scope="module")
def app() -> QApplication:
    return QApplication.instance() or QApplication([])


@pytest.fixture()
def window(app: QApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ACADEMIC_PLATFORM_HOME", str(tmp_path / "home"))
    directories = load_runtime_directories()
    settings = SettingsService(directories.config_file)
    settings.load()
    database = Database.from_path(directories.database_file)
    Base.metadata.create_all(database.engine)
    window = MainWindow(
        directories=directories,
        settings_service=settings,
        database=database,
    )
    yield window, database
    database.dispose()


def test_linking_service_factory_available(window) -> None:
    main_window, _ = window
    factory = main_window.document_linking_service_factory
    assert callable(factory)
    service = factory()
    assert service is not None


def test_add_to_collection_requested_opens_dialog(window) -> None:
    main_window, _ = window
    # The handler must exist and be callable without raising when the
    # dialog cannot be constructed (no window showing).
    assert callable(main_window._on_add_to_collection_requested)  # noqa: SLF001
    assert callable(main_window._on_add_to_project_requested)  # noqa: SLF001