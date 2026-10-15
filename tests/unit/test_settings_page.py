"""Tests for the Settings page composition."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QTabWidget  # noqa: E402

from academic_platform.app.configuration import load_runtime_directories  # noqa: E402
from academic_platform.app.settings import SettingsService  # noqa: E402
from academic_platform.ui.pages.settings import SettingsPage  # noqa: E402


@pytest.fixture(scope="module")
def app() -> QApplication:
    return QApplication.instance() or QApplication([])


@pytest.fixture()
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ACADEMIC_PLATFORM_HOME", str(tmp_path / "home"))
    directories = load_runtime_directories()
    service = SettingsService(directories.config_file)
    service.load()
    return directories, service


def test_page_has_six_tabs(app: QApplication, env) -> None:
    directories, service = env
    page = SettingsPage(settings_service=service, directories=directories)
    tabs = page.findChild(QTabWidget, "settingsTabs")
    assert tabs is not None
    assert tabs.count() == 6


def test_tab_labels(app: QApplication, env) -> None:
    directories, service = env
    page = SettingsPage(settings_service=service, directories=directories)
    tabs = page.findChild(QTabWidget, "settingsTabs")
    assert tabs is not None
    labels = [tabs.tabText(i) for i in range(tabs.count())]
    assert labels == [
        "General",
        "Appearance",
        "Search",
        "AI Providers",
        "Privacy",
        "Advanced",
    ]


def test_external_change_reloads_controls(app: QApplication, env) -> None:
    directories, service = env
    page = SettingsPage(settings_service=service, directories=directories)
    service.update_section("appearance", theme="dark")
    # After an external update, the appearance tab must reflect the new value.
    from PySide6.QtWidgets import QComboBox

    combo = page.findChild(QComboBox, "settingsAppearanceTheme")
    assert combo is not None
    assert combo.currentData() == "dark"


def test_page_title_and_subtitle(app: QApplication, env) -> None:
    directories, service = env
    page = SettingsPage(settings_service=service, directories=directories)
    assert page.title == "Settings"
    assert page.subtitle