"""Tests for the Appearance settings tab."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QCheckBox, QComboBox, QDoubleSpinBox  # noqa: E402

from academic_platform.app.settings import SettingsService, ThemeMode  # noqa: E402
from academic_platform.ui.pages.settings.appearance_tab import (  # noqa: E402
    AppearanceSettingsTab,
)


@pytest.fixture(scope="module")
def app() -> QApplication:
    return QApplication.instance() or QApplication([])


@pytest.fixture()
def service(tmp_path: Path) -> SettingsService:
    svc = SettingsService(tmp_path / "config.toml")
    svc.load()
    return svc


def test_theme_default_system(app: QApplication, service: SettingsService) -> None:
    tab = AppearanceSettingsTab(service)
    combo = tab.findChild(QComboBox, "settingsAppearanceTheme")
    assert combo is not None
    assert combo.currentData() == ThemeMode.SYSTEM.value


def test_theme_change_persists(app: QApplication, service: SettingsService) -> None:
    tab = AppearanceSettingsTab(service)
    combo = tab.findChild(QComboBox, "settingsAppearanceTheme")
    assert combo is not None
    for index in range(combo.count()):
        if combo.itemData(index) == ThemeMode.DARK.value:
            combo.setCurrentIndex(index)
            break
    assert service.settings.appearance.theme is ThemeMode.DARK


def test_font_scale_clamped(app: QApplication, service: SettingsService) -> None:
    tab = AppearanceSettingsTab(service)
    scale = tab.findChild(QDoubleSpinBox, "settingsAppearanceFontScale")
    assert scale is not None
    assert scale.minimum() == 0.75
    assert scale.maximum() == 2.0


def test_density_persists(app: QApplication, service: SettingsService) -> None:
    tab = AppearanceSettingsTab(service)
    combo = tab.findChild(QComboBox, "settingsAppearanceDensity")
    assert combo is not None
    for index in range(combo.count()):
        if combo.itemData(index) == "compact":
            combo.setCurrentIndex(index)
            break
    assert service.settings.appearance.density == "compact"


def test_show_labels_toggle(app: QApplication, service: SettingsService) -> None:
    tab = AppearanceSettingsTab(service)
    checkbox = tab.findChild(QCheckBox, "settingsAppearanceShowLabels")
    assert checkbox is not None
    checkbox.setChecked(False)
    assert service.settings.appearance.show_sidebar_labels is False