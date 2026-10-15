"""Pydantic schemas for the audit event model."""

from __future__ import annotations

import datetime as dt

from pydantic import Field

from academic_platform.infrastructure.database.schemas._base import PersistenceSchema


class AuditEventCreate(PersistenceSchema):
    """Payload accepted when appending an audit event."""

    actor: str = Field(default="system", max_length=64)
    action: str = Field(min_length=1, max_length=64)
    target_type: str | None = Field(default=None, max_length=64)
    target_identifier: str | None = Field(default=None, max_length=64)
    summary: str = Field(default="", max_length=512)
    payload_json: str | None = None
    occurred_at: dt.datetime | None = None


class AuditEventRead(PersistenceSchema):
    """Payload returned when reading an audit event."""

    id: int
    actor: str
    action: str
    target_type: str | None
    target_identifier: str | None
    summary: str
    payload_json: str | None
    occurred_at: dt.datetime
    created_at: dt.datetime
    updated_at: dt.datetime