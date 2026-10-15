"""Tests for the ResearchProject Pydantic schemas."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from academic_platform.infrastructure.database.schemas import (
    ResearchProjectCreate,
    ResearchProjectUpdate,
)


def test_create_defaults() -> None:
    payload = ResearchProjectCreate(key="p1")
    assert payload.title == ""
    assert payload.stage == "idea"


@pytest.mark.parametrize(
    "bad_key",
    ["", "P1", "p 1", "-p1", "p1!"],
)
def test_create_rejects_invalid_key(bad_key: str) -> None:
    with pytest.raises(ValidationError):
        ResearchProjectCreate(key=bad_key)


@pytest.mark.parametrize(
    "bad_stage",
    ["", "Bogus", "IDEA"],
)
def test_create_rejects_invalid_stage(bad_stage: str) -> None:
    with pytest.raises(ValidationError):
        ResearchProjectCreate(key="p1", stage=bad_stage)


def test_update_all_optional() -> None:
    payload = ResearchProjectUpdate()
    assert payload.title is None
    assert payload.stage is None


def test_update_rejects_invalid_stage() -> None:
    with pytest.raises(ValidationError):
        ResearchProjectUpdate(stage="bogus")