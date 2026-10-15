"""Pydantic schemas for the search source model."""

from __future__ import annotations

import datetime as dt

from pydantic import Field, field_validator

from academic_platform.infrastructure.database.schemas._base import PersistenceSchema

_VALID_SOURCE_TYPES = {"builtin", "user_defined"}
_VALID_AUTH_TYPES = {"none", "api_key", "bearer_token"}
_VALID_HTTP_METHODS = {"GET", "POST"}


class SearchSourceCreate(PersistenceSchema):
    """Payload accepted when creating a search source."""

    key: str = Field(min_length=1, max_length=64)
    provider_key: str = Field(min_length=1, max_length=64)
    display_name: str = Field(min_length=1, max_length=255)
    source_type: str = Field(max_length=32)
    base_url: str = Field(min_length=1, max_length=2048)
    endpoint: str = Field(default="", max_length=2048)
    http_method: str = Field(default="GET", max_length=16)
    parameter_map_json: str = "{}"
    capabilities_json: str = "{}"
    rate_limit_json: str | None = None
    auth_type: str = Field(default="none", max_length=32)
    credential_reference: str | None = Field(default=None, max_length=128)
    enabled: bool = True
    timeout_seconds: int = Field(default=20, ge=1, le=180)
    result_limit: int = Field(default=50, ge=1, le=500)

    @field_validator("source_type")
    @classmethod
    def _check_type(cls, value: str) -> str:
        if value not in _VALID_SOURCE_TYPES:
            raise ValueError(f"source_type must be one of {sorted(_VALID_SOURCE_TYPES)}")
        return value

    @field_validator("auth_type")
    @classmethod
    def _check_auth(cls, value: str) -> str:
        if value not in _VALID_AUTH_TYPES:
            raise ValueError(f"auth_type must be one of {sorted(_VALID_AUTH_TYPES)}")
        return value

    @field_validator("http_method")
    @classmethod
    def _check_method(cls, value: str) -> str:
        upper = value.upper()
        if upper not in _VALID_HTTP_METHODS:
            raise ValueError(
                f"http_method must be one of {sorted(_VALID_HTTP_METHODS)}"
            )
        return upper


class SearchSourceUpdate(PersistenceSchema):
    """Payload accepted when updating a search source."""

    display_name: str | None = Field(default=None, max_length=255)
    base_url: str | None = Field(default=None, max_length=2048)
    endpoint: str | None = Field(default=None, max_length=2048)
    http_method: str | None = Field(default=None, max_length=16)
    parameter_map_json: str | None = None
    capabilities_json: str | None = None
    rate_limit_json: str | None = None
    auth_type: str | None = Field(default=None, max_length=32)
    credential_reference: str | None = Field(default=None, max_length=128)
    enabled: bool | None = None
    timeout_seconds: int | None = Field(default=None, ge=1, le=180)
    result_limit: int | None = Field(default=None, ge=1, le=500)
    last_tested_at: str | None = Field(default=None, max_length=64)
    last_error: str | None = None

    @field_validator("auth_type")
    @classmethod
    def _check_auth(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if value not in _VALID_AUTH_TYPES:
            raise ValueError(f"auth_type must be one of {sorted(_VALID_AUTH_TYPES)}")
        return value

    @field_validator("http_method")
    @classmethod
    def _check_method(cls, value: str | None) -> str | None:
        if value is None:
            return None
        upper = value.upper()
        if upper not in _VALID_HTTP_METHODS:
            raise ValueError(
                f"http_method must be one of {sorted(_VALID_HTTP_METHODS)}"
            )
        return upper


class SearchSourceRead(PersistenceSchema):
    """Payload returned when reading a search source."""

    id: int
    key: str
    provider_key: str
    display_name: str
    source_type: str
    base_url: str
    endpoint: str
    http_method: str
    parameter_map_json: str
    capabilities_json: str
    rate_limit_json: str | None
    auth_type: str
    credential_reference: str | None
    enabled: bool
    timeout_seconds: int
    result_limit: int
    last_tested_at: str | None
    last_error: str | None
    created_at: dt.datetime
    updated_at: dt.datetime
    version: int

    @field_validator("enabled", mode="before")
    @classmethod
    def _coerce_int_bool(cls, value: object) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, int):
            return value != 0
        return bool(value)