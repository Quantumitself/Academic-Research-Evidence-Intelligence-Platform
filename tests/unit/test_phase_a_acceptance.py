"""Phase A acceptance criteria as automated tests.

These tests express the acceptance criteria in the same language as the
Phase A acceptance document. They are intentionally broader than the
component tests: they exercise the shell, the settings service, the
stylesheet builder, the notification service, and the dialog factory
together.

The tests use the offscreen Qt platform plugin and a temporary home
directory. They do not touch the user's data.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from academic_platform.app.configuration import load_runtime_directories  # noqa: E402
from academic_platform.app.settings import SettingsService  # noqa: E402
from academic_platform.app.settings.schema import ThemeMode  # noqa: E402
from academic_platform.ui.main_window import MainWindow  # noqa: E402
from academic_platform.ui.main_window_destinations import DESTINATIONS  # noqa: E402
from academic_platform.ui.notifications import NotificationHost, NotificationService  # noqa: E402
from academic_platform.ui.pages.base_page import BasePage  # noqa: E402
from academic_platform.ui.resources.styles import build_application_stylesheet  # noqa: E402
from academic_platform.infrastructure.database import Database  # noqa: E402
from academic_platform.infrastructure.database import Database


@pytest.fixture(scope="module")
def app() -> QApplication:
    return QApplication.instance() or QApplication([])


@pytest.fixture()
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ACADEMIC_PLATFORM_HOME", str(tmp_path / "home"))
    directories = load_runtime_directories()
    settings = SettingsService(directories.config_file)
    settings.load()
    database = Database.from_path(directories.database_file)
    yield directories, settings, database
    database.dispose()


def test_shell_constructs_with_all_destinations(
    app: QApplication, env
) -> None:
    directories, settings, database = env
    window = MainWindow(
        directories=directories,
        settings_service=settings,
        database=database,
    )
    expected = {destination.identifier for destination in DESTINATIONS}
    assert set(window._pages.keys()) == expected  # noqa: SLF001
    window.close()


def test_every_page_inherits_base_page(app: QApplication, env) -> None:
    directories, settings, database = env
    window = MainWindow(
        directories=directories,
        settings_service=settings,
        database=database,
    )
    for page in window._pages.values():  # noqa: SLF001
        assert isinstance(page, BasePage)
    window.close()


def test_navigation_reaches_every_destination(app: QApplication, env) -> None:
    directories, settings, database = env
    window = MainWindow(
        directories=directories,
        settings_service=settings,
        database=database,
    )
    for destination in DESTINATIONS:
        window.navigate_to(destination.identifier)
        assert window._current_identifier == destination.identifier  # noqa: SLF001
    window.close()


def test_status_bar_reflects_active_page(app: QApplication, env) -> None:
    directories, settings, database = env
    window = MainWindow(
        directories=directories,
        settings_service=settings,
        database=database,
    )
    window.navigate_to("library")
    message = window.statusBar().currentMessage()
    assert message == "My Library"
    window.close()


def test_stylesheet_builds_for_all_variants(app: QApplication) -> None:
    for theme in (ThemeMode.LIGHT, ThemeMode.DARK):
        for density in ("compact", "comfortable", "spacious"):
            sheet = build_application_stylesheet(theme, 1.0, density)
            assert sheet.strip()
            assert "#pageHeader" in sheet
            assert "#sectionCard" in sheet


def test_notification_host_constructs_and_renders(
    app: QApplication, env
) -> None:
    from PySide6.QtWidgets import QFrame, QWidget

    parent = QWidget()
    parent.resize(800, 600)
    service = NotificationService()
    host = NotificationHost(parent=parent, service=service)
    service.publish("Hello", "World")
    cards = host.container().findChildren(QFrame, "notificationCard")
    assert cards


def test_settings_persist_across_reload(app: QApplication, env) -> None:
    directories, settings, _database = env
    settings.update_section("appearance", theme="dark")
    reloaded = SettingsService(directories.config_file)
    reloaded.load()
    assert reloaded.settings.appearance.theme is ThemeMode.DARK


def test_dialogs_construct_without_error(app: QApplication) -> None:
    from academic_platform.ui.dialogs.dialog_factory import DialogFactory
    from academic_platform.ui.dialogs.form_dialog import FormField, FormFieldKind

    DialogFactory.message_dialog(None, "T", "M")
    DialogFactory.confirm_dialog(None, "T", "Q")
    DialogFactory.prompt_dialog(None, "T", "L")
    DialogFactory.form_dialog(
        None,
        "T",
        (FormField("a", "A", FormFieldKind.TEXT),),
    )
    DialogFactory.progress_dialog(None, "T", total=5)


def test_placeholder_visibility_uses_is_visible_to(app: QApplication, env) -> None:
    """Guard against the ``isVisible()`` pitfall documented in the notes."""
    from academic_platform.ui.components.empty_state import EmptyState

    state = EmptyState("T", "M", action_label="Go")
    # isVisibleTo(parent) must report the state's own visibility even when
    # no ancestor has been shown.
    assert state.action_button.isVisibleTo(state)