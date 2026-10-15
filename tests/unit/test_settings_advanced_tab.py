"""Tests for the Advanced settings tab."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QCheckBox, QLineEdit, QPushButton  # noqa: E402

from academic_platform.app.configuration import load_runtime_directories  # noqa: E402
from academic_platform.app.settings import SettingsService  # noqa: E402
from academic_platform.ui.pages.settings.advanced_tab import AdvancedSettingsTab  # noqa: E402


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


def test_offline_toggle(app: QApplication, env) -> None:
    directories, service = env
    tab = AdvancedSettingsTab(service, directories)
    checkbox = tab.findChild(QCheckBox, "settingsAdvancedOffline")
    assert checkbox is not None
    checkbox.setChecked(True)
    assert service.settings.network.offline_mode is True


def test_system_proxy_toggle(app: QApplication, env) -> None:
    directories, service = env
    tab = AdvancedSettingsTab(service, directories)
    checkbox = tab.findChild(QCheckBox, "settingsAdvancedSystemProxy")
    assert checkbox is not None
    checkbox.setChecked(False)
    assert service.settings.network.use_system_proxy is False


def test_user_agent_suffix_persists(app: QApplication, env) -> None:
    directories, service = env
    tab = AdvancedSettingsTab(service, directories)
    field = tab.findChild(QLineEdit, "settingsAdvancedUserAgentSuffix")
    assert field is not None
    field.setText(" (test)")
    field.editingFinished.emit()
    assert service.settings.network.user_agent_suffix == "(test)"


def test_reset_button_exists(app: QApplication, env) -> None:
    directories, service = env
    tab = AdvancedSettingsTab(service, directories)
    button = tab.findChild(QPushButton, "settingsAdvancedReset")
    assert button is not None
    assert button.isEnabled()