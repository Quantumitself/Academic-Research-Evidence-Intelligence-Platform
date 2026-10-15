"""Shared configuration for persistence schemas.

Persistence schemas differ from API schemas in one important respect:
they accept ORM model instances as input. The ``from_attributes`` flag on
``model_config`` enables ``model_validate`` to accept ORM objects directly
without an intermediate dictionary conversion.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class PersistenceSchema(BaseModel):
    """Base class for persistence schemas."""

    model_config = ConfigDict(
        from_attributes=True,
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )