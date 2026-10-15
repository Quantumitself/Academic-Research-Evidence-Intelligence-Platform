"""Tests for the Collection Pydantic schemas."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from academic_platform.infrastructure.database.schemas import (
    CollectionCreate,
    CollectionItemCreate,
)


def test_manual_collection_defaults() -> None:
    payload = CollectionCreate(key="c1")
    assert payload.kind == "manual"
    assert payload.project_id is None


def test_project_collection_requires_project() -> None:
    with pytest.raises(ValidationError):
        CollectionCreate(key="c1", kind="project")


def test_manual_collection_rejects_project() -> None:
    with pytest.raises(ValidationError):
        CollectionCreate(key="c1", kind="manual", project_id=1)


def test_project_collection_accepts_project() -> None:
    payload = CollectionCreate(key="c1", kind="project", project_id=1)
    assert payload.project_id == 1


def test_item_create_rejects_invalid_type() -> None:
    with pytest.raises(ValidationError):
        CollectionItemCreate(
            collection_id=1,
            item_type="bogus",
            item_identifier="x",
        )


def test_item_create_accepts_valid_type() -> None:
    payload = CollectionItemCreate(
        collection_id=1,
        item_type="publication",
        item_identifier="pub-1",
    )
    assert payload.item_type == "publication"