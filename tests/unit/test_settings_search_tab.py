"""Tests for the Search settings tab."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QCheckBox, QDoubleSpinBox, QSpinBox  # noqa: E402

from academic_platform.app.settings import SettingsService  # noqa: E402
from academic_platform.ui.pages.settings.search_tab import SearchSettingsTab  # noqa: E402


@pytest.fixture(scope="module")
def app() -> QApplication:
    return QApplication.instance() or QApplication([])


@pytest.fixture()
def service(tmp_path: Path) -> SettingsService:
    svc = SettingsService(tmp_path / "config.toml")
    svc.load()
    return svc


def test_result_limit_persists(app: QApplication, service: SettingsService) -> None:
    tab = SearchSettingsTab(service)
    spin = tab.findChild(QSpinBox, "settingsSearchResultLimit")
    assert spin is not None
    spin.setValue(120)
    assert service.settings.search.default_result_limit == 120


def test_timeout_persists(app: QApplication, service: SettingsService) -> None:
    tab = SearchSettingsTab(service)
    spin = tab.findChild(QDoubleSpinBox, "settingsSearchTimeout")
    assert spin is not None
    spin.setValue(45.0)
    assert service.settings.search.request_timeout_seconds == 45.0


def test_concurrency_persists(app: QApplication, service: SettingsService) -> None:
    tab = SearchSettingsTab(service)
    spin = tab.findChild(QSpinBox, "settingsSearchConcurrency")
    assert spin is not None
    spin.setValue(8)
    assert service.settings.search.max_concurrent_sources == 8


def test_https_required_by_default(app: QApplication, service: SettingsService) -> None:
    tab = SearchSettingsTab(service)
    checkbox = tab.findChild(QCheckBox, "settingsSearchRequireHttps")
    assert checkbox is not None
    assert checkbox.isChecked()
    assert service.settings.search.require_https is True


def test_dedup_toggle(app: QApplication, service: SettingsService) -> None:
    tab = SearchSettingsTab(service)
    checkbox = tab.findChild(QCheckBox, "settingsSearchDeduplicate")
    assert checkbox is not None
    checkbox.setChecked(False)
    assert service.settings.search.deduplicate_results is False