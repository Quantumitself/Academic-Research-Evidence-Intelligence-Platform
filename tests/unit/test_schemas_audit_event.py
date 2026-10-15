"""Tests for the AuditEvent Pydantic schemas."""

from __future__ import annotations

import datetime as dt

import pytest
from pydantic import ValidationError

from academic_platform.infrastructure.database.schemas import (
    AuditEventCreate,
    AuditEventRead,
)


def test_create_defaults() -> None:
    payload = AuditEventCreate(action="app.started")
    assert payload.actor == "system"
    assert payload.summary == ""


def test_create_requires_action() -> None:
    with pytest.raises(ValidationError):
        AuditEventCreate(action="")


def test_create_rejects_overlong_summary() -> None:
    with pytest.raises(ValidationError):
        AuditEventCreate(action="a", summary="x" * 600)


def test_read_from_attributes() -> None:
    class _Row:
        id = 1
        actor = "system"
        action = "app.started"
        target_type = None
        target_identifier = None
        summary = ""
        payload_json = None
        occurred_at = dt.datetime(2024, 1, 1)
        created_at = dt.datetime(2024, 1, 1)
        updated_at = dt.datetime(2024, 1, 1)

    payload = AuditEventRead.model_validate(_Row())
    assert payload.action == "app.started"