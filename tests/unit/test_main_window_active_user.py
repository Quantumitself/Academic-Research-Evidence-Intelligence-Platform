"""Tests for the active user key exposure on the main window."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from academic_platform.app.configuration import load_runtime_directories  # noqa: E402
from academic_platform.app.settings import SettingsService  # noqa: E402
from academic_platform.infrastructure.database import Database  # noqa: E402
from academic_platform.infrastructure.database.base import Base  # noqa: E402
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
    yield window
    database.dispose()


def test_active_user_key_defaults_to_none(window: MainWindow) -> None:
    assert window.active_user_key is None


def test_refresh_active_user_reads_database(window: MainWindow) -> None:
    # Populate a profile and activate it through the bridge.
    from academic_platform.application.settings_persistence import (
        SettingsPersistenceBridge,
    )
    from academic_platform.infrastructure.database.models import UserProfile
    from academic_platform.infrastructure.repositories.app_settings_repository import (
        AppSettingsRepository,
    )
    from academic_platform.infrastructure.repositories.user_profile_repository import (
        UserProfileRepository,
    )

    with window.database.session() as session:
        UserProfileRepository(session).add(UserProfile(key="alice"))

    with window.database.session() as session:
        bridge = SettingsPersistenceBridge(
            settings_service=window._settings_service,  # noqa: SLF001
            app_settings_repository=AppSettingsRepository(session),
            user_profile_repository=UserProfileRepository(session),
        )
        bridge.set_active_user("alice")

    assert window.refresh_active_user() == "alice"
    assert window.active_user_key == "alice"


def test_settings_change_refreshes_active_user(window: MainWindow) -> None:
    window._settings_service.update_section("general", language="fr")  # noqa: SLF001
    # The value is refreshed through the observer; it should still be
    # consistent with the database, which is None in this test.
    assert window.active_user_key is None