"""Tests for the AI Pydantic schemas."""

from __future__ import annotations

import datetime as dt

import pytest
from pydantic import ValidationError

from academic_platform.infrastructure.database.schemas import (
    AIInvocationCreate,
    AIInvocationRead,
    AIModelCreate,
    AIProviderCreate,
    AIProviderUpdate,
    AITaskRoutingCreate,
)


def test_provider_create_defaults() -> None:
    payload = AIProviderCreate(
        key="local",
        display_name="Local",
        provider_kind="local_gguf",
    )
    assert payload.auth_type == "none"
    assert payload.enabled is True
    assert payload.default_for_tasks_json == "[]"


def test_provider_create_rejects_bad_kind() -> None:
    with pytest.raises(ValidationError):
        AIProviderCreate(
            key="local",
            display_name="Local",
            provider_kind="bogus",
        )


def test_provider_update_all_optional() -> None:
    payload = AIProviderUpdate()
    assert payload.display_name is None


def test_provider_update_rejects_bad_health() -> None:
    with pytest.raises(ValidationError):
        AIProviderUpdate(health_state="bogus")


def test_model_create_defaults() -> None:
    payload = AIModelCreate(provider_id=1, model_identifier="m")
    assert payload.enabled is True


def test_task_routing_create_defaults() -> None:
    payload = AITaskRoutingCreate(task_key="t")
    assert payload.provider_id is None
    assert payload.parameters_json == "{}"


def test_task_routing_rejects_out_of_range_temperature() -> None:
    with pytest.raises(ValidationError):
        AITaskRoutingCreate(task_key="t", temperature=3.0)


def test_invocation_create_requires_status() -> None:
    with pytest.raises(ValidationError):
        AIInvocationCreate(
            task_key="t",
            started_at=dt.datetime(2024, 1, 1),
            status="",
        )


def test_invocation_create_rejects_bad_status() -> None:
    with pytest.raises(ValidationError):
        AIInvocationCreate(
            task_key="t",
            started_at=dt.datetime(2024, 1, 1),
            status="bogus",
        )


def test_invocation_read_from_attributes() -> None:
    class _Row:
        id = 1
        task_key = "t"
        provider_id = None
        model_id = None
        provider_key_snapshot = "local"
        model_identifier_snapshot = "m"
        prompt_template_version = None
        status = "ok"
        started_at = dt.datetime(2024, 1, 1)
        finished_at = None
        duration_ms = 100
        input_size_bytes = 10
        output_size_bytes = 20
        input_tokens = 5
        output_tokens = 10
        total_tokens = 15
        request_id = None
        error_message = None
        extra_json = None
        created_at = dt.datetime(2024, 1, 1)
        updated_at = dt.datetime(2024, 1, 1)

    payload = AIInvocationRead.model_validate(_Row())
    assert payload.status == "ok"