"""Tests for the stylesheet builder."""

from __future__ import annotations

from academic_platform.app.settings.schema import ThemeMode
from academic_platform.ui.resources.styles import build_application_stylesheet


def test_builder_returns_non_empty_string() -> None:
    sheet = build_application_stylesheet(ThemeMode.LIGHT, 1.0, "comfortable")
    assert isinstance(sheet, str)
    assert sheet.strip()
    assert "#navigationBar" in sheet
    assert "#sectionCard" in sheet


def test_theme_changes_palette() -> None:
    light = build_application_stylesheet(ThemeMode.LIGHT, 1.0, "comfortable")
    dark = build_application_stylesheet(ThemeMode.DARK, 1.0, "comfortable")
    assert light != dark


def test_font_scale_changes_font_size() -> None:
    normal = build_application_stylesheet(ThemeMode.LIGHT, 1.0, "comfortable")
    large = build_application_stylesheet(ThemeMode.LIGHT, 1.5, "comfortable")
    assert normal != large


def test_density_changes_padding() -> None:
    compact = build_application_stylesheet(ThemeMode.LIGHT, 1.0, "compact")
    spacious = build_application_stylesheet(ThemeMode.LIGHT, 1.0, "spacious")
    assert compact != spacious


def test_unknown_density_falls_back_to_comfortable() -> None:
    unknown = build_application_stylesheet(ThemeMode.LIGHT, 1.0, "unknown")
    comfortable = build_application_stylesheet(ThemeMode.LIGHT, 1.0, "comfortable")
    assert unknown == comfortable


def test_system_theme_falls_back_to_light() -> None:
    system = build_application_stylesheet(ThemeMode.SYSTEM, 1.0, "comfortable")
    light = build_application_stylesheet(ThemeMode.LIGHT, 1.0, "comfortable")
    assert system == light


def test_legacy_constant_matches_builder() -> None:
    from academic_platform.ui.resources.styles import APPLICATION_STYLESHEET

    expected = build_application_stylesheet(ThemeMode.LIGHT, 1.0, "comfortable")
    assert APPLICATION_STYLESHEET == expected