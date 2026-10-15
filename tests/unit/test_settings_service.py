"""Tests for the settings service."""

from __future__ import annotations

from pathlib import Path

import pytest

from academic_platform.app.settings import (
    SETTINGS_SCHEMA_VERSION,
    SettingsError,
    SettingsSchema,
    SettingsService,
    ThemeMode,
)


def test_load_creates_default_file(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    service = SettingsService(path)
    result = service.load()
    assert result.created is True
    assert result.migrated_from is None
    assert path.exists()
    assert "schema_version" in path.read_text(encoding="utf-8")


def test_load_existing_file(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    path.write_text(
        f"schema_version = {SETTINGS_SCHEMA_VERSION}\n"
        "[appearance]\n"
        'theme = "dark"\n',
        encoding="utf-8",
    )
    service = SettingsService(path)
    result = service.load()
    assert result.created is False
    assert result.settings.appearance.theme is ThemeMode.DARK


def test_load_invalid_toml_raises(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    path.write_text("this is not = valid = toml\n", encoding="utf-8")
    service = SettingsService(path)
    with pytest.raises(SettingsError):
        service.load()


def test_load_newer_schema_version_raises(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    path.write_text(
        f"schema_version = {SETTINGS_SCHEMA_VERSION + 5}\n",
        encoding="utf-8",
    )
    service = SettingsService(path)
    with pytest.raises(SettingsError):
        service.load()


def test_load_unknown_field_raises(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    path.write_text(
        f"schema_version = {SETTINGS_SCHEMA_VERSION}\n"
        'unknown_field = "x"\n',
        encoding="utf-8",
    )
    service = SettingsService(path)
    with pytest.raises(SettingsError):
        service.load()


def test_save_and_reload_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    service = SettingsService(path)
    service.load()
    service.update_section("appearance", theme="dark")

    reloaded = SettingsService(path)
    reloaded.load()
    assert reloaded.settings.appearance.theme is ThemeMode.DARK


def test_save_creates_backup(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    service = SettingsService(path)
    service.load()
    service.update_section("appearance", theme="dark")
    service.update_section("appearance", theme="light")
    backup = path.with_suffix(path.suffix + ".bak")
    assert backup.exists()
    assert "dark" in backup.read_text(encoding="utf-8")


def test_reset_to_defaults(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    service = SettingsService(path)
    service.load()
    service.update_section("appearance", theme="dark")
    service.reset_to_defaults()
    assert service.settings.appearance.theme is ThemeMode.SYSTEM


def test_observers_called_on_save(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    service = SettingsService(path)
    service.load()
    captured: list[SettingsSchema] = []
    service.add_observer(captured.append)
    service.update_section("appearance", theme="dark")
    assert len(captured) == 1
    assert captured[0].appearance.theme is ThemeMode.DARK


def test_observer_exception_does_not_break_save(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    service = SettingsService(path)
    service.load()
    captured: list[SettingsSchema] = []

    def bad_observer(_settings: SettingsSchema) -> None:
        raise RuntimeError("boom")

    service.add_observer(bad_observer)
    service.add_observer(captured.append)
    service.update_section("appearance", theme="dark")
    assert len(captured) == 1


def test_remove_observer(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    service = SettingsService(path)
    service.load()
    captured: list[SettingsSchema] = []
    service.add_observer(captured.append)
    service.remove_observer(captured.append)
    service.update_section("appearance", theme="dark")
    assert captured == []


def test_update_rejects_invalid_section_name(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    service = SettingsService(path)
    service.load()
    with pytest.raises(SettingsError):
        service.update_section("nonexistent", value=1)


def test_update_rejects_invalid_value(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    service = SettingsService(path)
    service.load()
    with pytest.raises(SettingsError):
        service.update_section("appearance", font_scale=99.0)


def test_settings_property_triggers_lazy_load(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    service = SettingsService(path)
    settings = service.settings
    assert settings.schema_version == SETTINGS_SCHEMA_VERSION
    assert path.exists()


def test_export_json_schema(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    service = SettingsService(path)
    schema = service.export_json_schema()
    assert schema["type"] == "object"
    assert "properties" in schema