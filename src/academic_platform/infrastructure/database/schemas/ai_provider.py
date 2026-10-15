"""Pydantic schemas for the AI provider, model, task routing, and invocation models."""

from __future__ import annotations

import datetime as dt

from pydantic import Field, field_validator

from academic_platform.infrastructure.database.schemas._base import PersistenceSchema

_VALID_PROVIDER_KINDS = {
    "local_gguf",
    "openai_compatible",
    "anthropic",
    "other",
}
_VALID_AUTH_TYPES = {"none", "api_key", "bearer_token"}
_VALID_HEALTH_STATES = {"unknown", "ok", "failed", "disabled"}
_VALID_INVOCATION_STATUSES = {"ok", "failed", "cancelled"}


def _validate_provider_kind(value: str) -> str:
    if value not in _VALID_PROVIDER_KINDS:
        raise ValueError(
            f"provider_kind must be one of {sorted(_VALID_PROVIDER_KINDS)}"
        )
    return value


def _validate_auth_type(value: str) -> str:
    if value not in _VALID_AUTH_TYPES:
        raise ValueError(f"auth_type must be one of {sorted(_VALID_AUTH_TYPES)}")
    return value


def _validate_health_state(value: str) -> str:
    if value not in _VALID_HEALTH_STATES:
        raise ValueError(
            f"health_state must be one of {sorted(_VALID_HEALTH_STATES)}"
        )
    return value


class AIProviderCreate(PersistenceSchema):
    """Payload accepted when creating an AI provider."""

    key: str = Field(min_length=1, max_length=64)
    display_name: str = Field(min_length=1, max_length=255)
    provider_kind: str = Field(max_length=32)
    endpoint_url: str = Field(default="", max_length=2048)
    model_file_path: str | None = Field(default=None, max_length=2048)
    auth_type: str = Field(default="none", max_length=32)
    credential_reference: str | None = Field(default=None, max_length=128)
    context_length: int | None = Field(default=None, ge=1)
    request_timeout_seconds: int = Field(default=120, ge=1, le=3600)
    max_retries: int = Field(default=2, ge=0, le=10)
    enabled: bool = True
    default_for_tasks_json: str = "[]"
    runtime_info_json: str | None = None

    @field_validator("provider_kind")
    @classmethod
    def _check_kind(cls, value: str) -> str:
        return _validate_provider_kind(value)

    @field_validator("auth_type")
    @classmethod
    def _check_auth(cls, value: str) -> str:
        return _validate_auth_type(value)


class AIProviderUpdate(PersistenceSchema):
    """Payload accepted when updating an AI provider."""

    display_name: str | None = Field(default=None, max_length=255)
    endpoint_url: str | None = Field(default=None, max_length=2048)
    model_file_path: str | None = Field(default=None, max_length=2048)
    auth_type: str | None = Field(default=None, max_length=32)
    credential_reference: str | None = Field(default=None, max_length=128)
    context_length: int | None = Field(default=None, ge=1)
    request_timeout_seconds: int | None = Field(default=None, ge=1, le=3600)
    max_retries: int | None = Field(default=None, ge=0, le=10)
    enabled: bool | None = None
    health_state: str | None = Field(default=None, max_length=16)
    last_tested_at: str | None = Field(default=None, max_length=64)
    last_error: str | None = None
    default_for_tasks_json: str | None = None
    runtime_info_json: str | None = None

    @field_validator("auth_type")
    @classmethod
    def _check_auth(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _validate_auth_type(value)

    @field_validator("health_state")
    @classmethod
    def _check_health(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _validate_health_state(value)


class AIProviderRead(PersistenceSchema):
    """Payload returned when reading an AI provider."""

    id: int
    key: str
    display_name: str
    provider_kind: str
    endpoint_url: str
    model_file_path: str | None
    auth_type: str
    credential_reference: str | None
    context_length: int | None
    request_timeout_seconds: int
    max_retries: int
    enabled: bool
    health_state: str
    last_tested_at: str | None
    last_error: str | None
    default_for_tasks_json: str
    runtime_info_json: str | None
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


class AIModelCreate(PersistenceSchema):
    """Payload accepted when registering a model."""

    provider_id: int = Field(ge=1)
    model_identifier: str = Field(min_length=1, max_length=255)
    display_name: str = Field(default="", max_length=255)
    context_length: int | None = Field(default=None, ge=1)
    max_output_tokens: int | None = Field(default=None, ge=1)
    capabilities_json: str = "{}"
    enabled: bool = True
    default_for_tasks_json: str = "[]"


class AIModelUpdate(PersistenceSchema):
    """Payload accepted when updating a model."""

    display_name: str | None = Field(default=None, max_length=255)
    context_length: int | None = Field(default=None, ge=1)
    max_output_tokens: int | None = Field(default=None, ge=1)
    capabilities_json: str | None = None
    enabled: bool | None = None
    health_state: str | None = Field(default=None, max_length=16)
    last_tested_at: str | None = Field(default=None, max_length=64)
    last_error: str | None = None
    default_for_tasks_json: str | None = None

    @field_validator("health_state")
    @classmethod
    def _check_health(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _validate_health_state(value)


class AIModelRead(PersistenceSchema):
    """Payload returned when reading a model."""

    id: int
    provider_id: int
    model_identifier: str
    display_name: str
    context_length: int | None
    max_output_tokens: int | None
    capabilities_json: str
    enabled: bool
    health_state: str
    last_tested_at: str | None
    last_error: str | None
    default_for_tasks_json: str
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


class AITaskRoutingCreate(PersistenceSchema):
    """Payload accepted when creating a task routing entry."""

    task_key: str = Field(min_length=1, max_length=64)
    provider_id: int | None = Field(default=None, ge=1)
    model_id: int | None = Field(default=None, ge=1)
    fallback_provider_id: int | None = Field(default=None, ge=1)
    fallback_model_id: int | None = Field(default=None, ge=1)
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    max_output_tokens: int | None = Field(default=None, ge=1)
    parameters_json: str = "{}"


class AITaskRoutingUpdate(PersistenceSchema):
    """Payload accepted when updating a task routing entry."""

    provider_id: int | None = Field(default=None, ge=1)
    model_id: int | None = Field(default=None, ge=1)
    fallback_provider_id: int | None = Field(default=None, ge=1)
    fallback_model_id: int | None = Field(default=None, ge=1)
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    max_output_tokens: int | None = Field(default=None, ge=1)
    parameters_json: str | None = None


class AITaskRoutingRead(PersistenceSchema):
    """Payload returned when reading a task routing entry."""

    id: int
    task_key: str
    provider_id: int | None
    model_id: int | None
    fallback_provider_id: int | None
    fallback_model_id: int | None
    temperature: float | None
    max_output_tokens: int | None
    parameters_json: str
    created_at: dt.datetime
    updated_at: dt.datetime
    version: int


class AIInvocationCreate(PersistenceSchema):
    """Payload accepted when appending an invocation record."""

    task_key: str = Field(min_length=1, max_length=64)
    provider_id: int | None = Field(default=None, ge=1)
    model_id: int | None = Field(default=None, ge=1)
    provider_key_snapshot: str = Field(default="", max_length=64)
    model_identifier_snapshot: str = Field(default="", max_length=255)
    prompt_template_version: str | None = Field(default=None, max_length=64)
    status: str = Field(max_length=16)
    started_at: dt.datetime
    finished_at: dt.datetime | None = None
    duration_ms: int | None = Field(default=None, ge=0)
    input_size_bytes: int | None = Field(default=None, ge=0)
    output_size_bytes: int | None = Field(default=None, ge=0)
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)
    request_id: str | None = Field(default=None, max_length=255)
    error_message: str | None = None
    extra_json: str | None = None

    @field_validator("status")
    @classmethod
    def _check_status(cls, value: str) -> str:
        if value not in _VALID_INVOCATION_STATUSES:
            raise ValueError(
                f"status must be one of {sorted(_VALID_INVOCATION_STATUSES)}"
            )
        return value


class AIInvocationRead(PersistenceSchema):
    """Payload returned when reading an invocation record."""

    id: int
    task_key: str
    provider_id: int | None
    model_id: int | None
    provider_key_snapshot: str
    model_identifier_snapshot: str
    prompt_template_version: str | None
    status: str
    started_at: dt.datetime
    finished_at: dt.datetime | None
    duration_ms: int | None
    input_size_bytes: int | None
    output_size_bytes: int | None
    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None
    request_id: str | None
    error_message: str | None
    extra_json: str | None
    created_at: dt.datetime
    updated_at: dt.datetime