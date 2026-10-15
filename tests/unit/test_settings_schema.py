"""Tests for the settings schema."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from academic_platform.app.settings.schema import (
    SETTINGS_SCHEMA_VERSION,
    SettingsSchema,
    ThemeMode,
)


def test_defaults_are_valid() -> None:
    settings = SettingsSchema()
    assert settings.schema_version == SETTINGS_SCHEMA_VERSION
    assert settings.appearance.theme is ThemeMode.SYSTEM
    assert settings.general.telemetry_enabled is False
    assert settings.library.default_import_mode == "copy"
    assert settings.search.require_https is True
    assert settings.ai.send_document_excerpts is False
    assert settings.privacy.redact_document_content_in_logs is True
    assert settings.network.offline_mode is False


def test_unknown_field_rejected() -> None:
    with pytest.raises(ValidationError):
        SettingsSchema.model_validate({"unknown_field": 1})


def test_unknown_section_rejected() -> None:
    with pytest.raises(ValidationError):
        SettingsSchema.model_validate({"unknown_section": {"a": 1}})


def test_out_of_range_values_rejected() -> None:
    with pytest.raises(ValidationError):
        SettingsSchema.model_validate({"appearance": {"font_scale": 5.0}})


def test_theme_literal_enforced() -> None:
    with pytest.raises(ValidationError):
        SettingsSchema.model_validate({"appearance": {"theme": "neon"}})


def test_schema_version_newer_than_supported_rejected() -> None:
    with pytest.raises(ValidationError):
        SettingsSchema.model_validate({"schema_version": SETTINGS_SCHEMA_VERSION + 1})


def test_language_normalized() -> None:
    settings = SettingsSchema.model_validate({"general": {"language": "EN_us"}})
    assert settings.general.language == "en-us"


def test_empty_language_rejected() -> None:
    with pytest.raises(ValidationError):
        SettingsSchema.model_validate({"general": {"language": "   "}})


def test_json_schema_is_generated() -> None:
    schema = SettingsSchema.model_json_schema()
    assert schema["type"] == "object"
    assert "properties" in schema
    assert "appearance" in schema["properties"]
    assert "network" in schema["properties"]