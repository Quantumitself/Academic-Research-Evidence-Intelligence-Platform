"""Tests for the AI Providers settings tab."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QCheckBox, QLineEdit  # noqa: E402

from academic_platform.app.settings import SettingsService  # noqa: E402
from academic_platform.ui.pages.settings.ai_providers_tab import (  # noqa: E402
    AIProvidersSettingsTab,
)


@pytest.fixture(scope="module")
def app() -> QApplication:
    return QApplication.instance() or QApplication([])


@pytest.fixture()
def service(tmp_path: Path) -> SettingsService:
    svc = SettingsService(tmp_path / "config.toml")
    svc.load()
    return svc


def test_default_provider_persists(app: QApplication, service: SettingsService) -> None:
    tab = AIProvidersSettingsTab(service)
    field = tab.findChild(QLineEdit, "settingsAIDefaultProvider")
    assert field is not None
    field.setText("local-llama")
    field.editingFinished.emit()
    assert service.settings.ai.default_provider_id == "local-llama"


def test_empty_provider_becomes_none(app: QApplication, service: SettingsService) -> None:
    tab = AIProvidersSettingsTab(service)
    field = tab.findChild(QLineEdit, "settingsAIDefaultProvider")
    assert field is not None
    field.setText("some")
    field.editingFinished.emit()
    field.setText("")
    field.editingFinished.emit()
    assert service.settings.ai.default_provider_id is None


def test_excerpts_default_off(app: QApplication, service: SettingsService) -> None:
    tab = AIProvidersSettingsTab(service)
    checkbox = tab.findChild(QCheckBox, "settingsAISendExcerpts")
    assert checkbox is not None
    assert not checkbox.isChecked()
    assert service.settings.ai.send_document_excerpts is False


def test_external_providers_toggle(app: QApplication, service: SettingsService) -> None:
    tab = AIProvidersSettingsTab(service)
    checkbox = tab.findChild(QCheckBox, "settingsAIAllowExternal")
    assert checkbox is not None
    checkbox.setChecked(False)
    assert service.settings.ai.allow_external_providers is False