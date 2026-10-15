"""Tests for the Search tab manage-sources button."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QPushButton  # noqa: E402

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


def test_manage_button_exists(app: QApplication, env) -> None:
    directories, service = env
    page = SettingsPage(settings_service=service, directories=directories)
    button = page.findChild(QPushButton, "settingsSearchSourcesManage")
    assert button is not None
    assert button.isEnabled()