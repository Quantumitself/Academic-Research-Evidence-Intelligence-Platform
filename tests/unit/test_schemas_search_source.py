"""Tests for the search source Pydantic schemas."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from academic_platform.infrastructure.database.schemas import (
    SearchSourceCreate,
    SearchSourceUpdate,
)


def _payload(**overrides) -> dict:
    base = {
        "key": "crossref",
        "provider_key": "crossref",
        "display_name": "Crossref",
        "source_type": "builtin",
        "base_url": "https://api.crossref.org",
    }
    base.update(overrides)
    return base


def test_create_defaults() -> None:
    payload = SearchSourceCreate(**_payload())
    assert payload.enabled is True
    assert payload.http_method == "GET"
    assert payload.timeout_seconds == 20


def test_create_rejects_invalid_source_type() -> None:
    with pytest.raises(ValidationError):
        SearchSourceCreate(**_payload(source_type="bogus"))


def test_create_rejects_invalid_auth_type() -> None:
    with pytest.raises(ValidationError):
        SearchSourceCreate(**_payload(auth_type="bogus"))


def test_create_normalizes_http_method() -> None:
    payload = SearchSourceCreate(**_payload(http_method="post"))
    assert payload.http_method == "POST"


def test_create_rejects_invalid_http_method() -> None:
    with pytest.raises(ValidationError):
        SearchSourceCreate(**_payload(http_method="PUT"))


def test_update_all_optional() -> None:
    payload = SearchSourceUpdate()
    assert payload.display_name is None


def test_update_rejects_invalid_auth_type() -> None:
    with pytest.raises(ValidationError):
        SearchSourceUpdate(auth_type="bogus")