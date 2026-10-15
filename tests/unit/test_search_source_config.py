"""Tests for the search source configuration value objects."""

from __future__ import annotations

from academic_platform.application.search_sources.source_config import (
    SourceConfig,
    SourceRecord,
)


def test_config_defaults() -> None:
    config = SourceConfig(
        key="x",
        provider_key="x",
        display_name="X",
        source_type="user_defined",
        base_url="https://x.invalid",
    )
    assert config.enabled is True
    assert config.auth_type == "none"
    assert config.timeout_seconds == 20
    assert config.result_limit == 50


def test_config_is_builtin_flag() -> None:
    builtin = SourceConfig(
        key="b",
        provider_key="b",
        display_name="B",
        source_type="builtin",
        base_url="https://b.invalid",
    )
    user = SourceConfig(
        key="u",
        provider_key="u",
        display_name="U",
        source_type="user_defined",
        base_url="https://u.invalid",
    )
    assert builtin.is_builtin is True
    assert user.is_builtin is False


def test_requires_credentials_flag() -> None:
    none_auth = SourceConfig(
        key="a",
        provider_key="a",
        display_name="A",
        source_type="user_defined",
        base_url="https://a.invalid",
    )
    api_key = SourceConfig(
        key="b",
        provider_key="b",
        display_name="B",
        source_type="user_defined",
        base_url="https://b.invalid",
        auth_type="api_key",
        credential_reference="cred-b",
    )
    assert none_auth.requires_credentials is False
    assert api_key.requires_credentials is True


def test_record_proxies_key() -> None:
    config = SourceConfig(
        key="x",
        provider_key="x",
        display_name="X",
        source_type="user_defined",
        base_url="https://x.invalid",
    )
    record = SourceRecord(id=1, config=config)
    assert record.key == "x"