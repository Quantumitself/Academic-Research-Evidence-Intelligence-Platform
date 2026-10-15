"""Tests for the ResearchQuestion Pydantic schemas."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from academic_platform.infrastructure.database.schemas import (
    ResearchQuestionCreate,
    ResearchQuestionRead,
)


def test_create_defaults() -> None:
    payload = ResearchQuestionCreate(project_id=1, text="Why?")
    assert payload.kind == "main"
    assert payload.is_primary is False


def test_create_rejects_empty_text() -> None:
    with pytest.raises(ValidationError):
        ResearchQuestionCreate(project_id=1, text="")


def test_create_rejects_invalid_kind() -> None:
    with pytest.raises(ValidationError):
        ResearchQuestionCreate(project_id=1, text="x", kind="bogus")


def test_read_coerces_int_to_bool() -> None:
    class _Row:
        id = 1
        project_id = 1
        text = "Why?"
        kind = "main"
        is_primary = 1
        position = 0
        created_at = __import__("datetime").datetime(2024, 1, 1)
        updated_at = __import__("datetime").datetime(2024, 1, 1)
        version = 1

    payload = ResearchQuestionRead.model_validate(_Row())
    assert payload.is_primary is True