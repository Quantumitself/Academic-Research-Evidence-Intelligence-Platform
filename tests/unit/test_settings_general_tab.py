"""Tests for the General settings tab."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QCheckBox, QLineEdit  # noqa: E402

from academic_platform.app.settings import SettingsService  # noqa: E402
from academic_platform.ui.pages.settings.general_tab import GeneralSettingsTab  # noqa: E402


@pytest.fixture(scope="module")
def app() -> QApplication:
    return QApplication.instance() or QApplication([])


@pytest.fixture()
def service(tmp_path: Path) -> SettingsService:
    svc = SettingsService(tmp_path / "config.toml")
    svc.load()
    return svc


def test_initial_population(app: QApplication, service: SettingsService) -> None:
    tab = GeneralSettingsTab(service)
    language = tab.findChild(QLineEdit, "settingsGeneralLanguage")
    assert language is not None
    assert language.text() == service.settings.general.language


def test_language_change_persists(app: QApplication, service: SettingsService) -> None:
    tab = GeneralSettingsTab(service)
    language = tab.findChild(QLineEdit, "settingsGeneralLanguage")
    assert language is not None
    language.setText("fr")
    language.editingFinished.emit()
    assert service.settings.general.language == "fr"


def test_telemetry_default_off(app: QApplication, service: SettingsService) -> None:
    tab = GeneralSettingsTab(service)
    telemetry = tab.findChild(QCheckBox, "settingsGeneralTelemetry")
    assert telemetry is not None
    assert not telemetry.isChecked()


def test_telemetry_toggle_persists(app: QApplication, service: SettingsService) -> None:
    tab = GeneralSettingsTab(service)
    telemetry = tab.findChild(QCheckBox, "settingsGeneralTelemetry")
    assert telemetry is not None
    telemetry.setChecked(True)
    assert service.settings.general.telemetry_enabled is True


def test_empty_language_falls_back(app: QApplication, service: SettingsService) -> None:
    tab = GeneralSettingsTab(service)
    language = tab.findChild(QLineEdit, "settingsGeneralLanguage")
    assert language is not None
    language.setText("")
    language.editingFinished.emit()
    assert service.settings.general.language == "en"