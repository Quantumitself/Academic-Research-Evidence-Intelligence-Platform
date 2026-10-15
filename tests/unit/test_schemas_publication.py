"""Tests for the publication Pydantic schemas."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from academic_platform.infrastructure.database.schemas import (
    PublicationCreate,
    PublicationUpdate,
)


def test_create_defaults() -> None:
    payload = PublicationCreate(key="pub-1")
    assert payload.title == ""
    assert payload.source_providers_json == "[]"


def test_create_rejects_out_of_range_year() -> None:
    with pytest.raises(ValidationError):
        PublicationCreate(key="pub-1", year=99999)


def test_update_all_optional() -> None:
    payload = PublicationUpdate()
    assert payload.title is None