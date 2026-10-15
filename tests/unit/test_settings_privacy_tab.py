"""Tests for the Privacy settings tab."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QCheckBox, QComboBox, QSpinBox  # noqa: E402

from academic_platform.app.settings import SettingsService  # noqa: E402
from academic_platform.ui.pages.settings.privacy_tab import PrivacySettingsTab  # noqa: E402


@pytest.fixture(scope="module")
def app() -> QApplication:
    return QApplication.instance() or QApplication([])


@pytest.fixture()
def service(tmp_path: Path) -> SettingsService:
    svc = SettingsService(tmp_path / "config.toml")
    svc.load()
    return svc


def test_log_level_default(app: QApplication, service: SettingsService) -> None:
    tab = PrivacySettingsTab(service)
    combo = tab.findChild(QComboBox, "settingsPrivacyLogLevel")
    assert combo is not None
    assert combo.currentData() == "INFO"


def test_log_level_change_persists(app: QApplication, service: SettingsService) -> None:
    tab = PrivacySettingsTab(service)
    combo = tab.findChild(QComboBox, "settingsPrivacyLogLevel")
    assert combo is not None
    for index in range(combo.count()):
        if combo.itemData(index) == "DEBUG":
            combo.setCurrentIndex(index)
            break
    assert service.settings.privacy.log_level == "DEBUG"


def test_redact_default_on(app: QApplication, service: SettingsService) -> None:
    tab = PrivacySettingsTab(service)
    checkbox = tab.findChild(QCheckBox, "settingsPrivacyRedact")
    assert checkbox is not None
    assert checkbox.isChecked()


def test_retention_persists(app: QApplication, service: SettingsService) -> None:
    tab = PrivacySettingsTab(service)
    spin = tab.findChild(QSpinBox, "settingsPrivacyLogRetention")
    assert spin is not None
    spin.setValue(30)
    assert service.settings.privacy.log_retention_days == 30