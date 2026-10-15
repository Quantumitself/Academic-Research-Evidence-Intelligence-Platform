"""Tests for the form helpers used by the sources dialog."""

from __future__ import annotations

from academic_platform.ui.pages.settings.sources_dialog import (
    _config_from_form_values,
    _changes_from_form_values,
    _validate_integer_range,
    _validate_key,
    _validate_required,
)


def test_validate_key_accepts_valid() -> None:
    assert _validate_key("crossref") is None
    assert _validate_key("my-source_2") is None


def test_validate_key_rejects_empty() -> None:
    assert _validate_key("") is not None


def test_validate_key_rejects_uppercase() -> None:
    assert _validate_key("Crossref") is not None


def test_validate_key_rejects_invalid_character() -> None:
    assert _validate_key("cross ref") is not None


def test_validate_key_rejects_leading_punctuation() -> None:
    assert _validate_key("-source") is not None


def test_validate_required_accepts_nonempty() -> None:
    validator = _validate_required("display_name")
    assert validator("Crossref") is None


def test_validate_required_rejects_empty() -> None:
    validator = _validate_required("display_name")
    result = validator("   ")
    assert result is not None


def test_validate_integer_range_accepts_in_range() -> None:
    validator = _validate_integer_range("timeout_seconds", 1, 180)
    assert validator("30") is None


def test_validate_integer_range_rejects_below() -> None:
    validator = _validate_integer_range("timeout_seconds", 1, 180)
    assert validator("0") is not None


def test_validate_integer_range_rejects_above() -> None:
    validator = _validate_integer_range("timeout_seconds", 1, 180)
    assert validator("500") is not None


def test_validate_integer_range_rejects_noninteger() -> None:
    validator = _validate_integer_range("timeout_seconds", 1, 180)
    assert validator("abc") is not None


def test_config_from_form_values() -> None:
    config = _config_from_form_values(
        {
            "key": "example",
            "provider_key": "example",
            "display_name": "Example",
            "base_url": "https://example.invalid",
            "endpoint": "search",
            "timeout_seconds": "15",
            "result_limit": "25",
        }
    )
    assert config.key == "example"
    assert config.source_type == "user_defined"
    assert config.timeout_seconds == 15
    assert config.result_limit == 25


def test_config_from_form_values_defaults() -> None:
    config = _config_from_form_values(
        {
            "key": "example",
            "provider_key": "example",
            "display_name": "Example",
            "base_url": "https://example.invalid",
        }
    )
    assert config.timeout_seconds == 30
    assert config.result_limit == 50


def test_changes_from_form_values_strips_empty() -> None:
    changes = _changes_from_form_values(
        {
            "display_name": "New Name",
            "base_url": "",
            "endpoint": "  ",
            "timeout_seconds": "60",
            "result_limit": "100",
        }
    )
    assert changes["display_name"] == "New Name"
    assert "base_url" not in changes
    assert "endpoint" not in changes
    assert changes["timeout_seconds"] == 60
    assert changes["result_limit"] == 100


def test_changes_from_form_values_rejects_noninteger() -> None:
    import pytest

    with pytest.raises(ValueError):
        _changes_from_form_values({"timeout_seconds": "abc"})