"""Specifications for the AI provider and model repositories."""

from __future__ import annotations

from academic_platform.infrastructure.database.models import (
    AIInvocation,
    AIModel,
    AIProvider,
)
from academic_platform.infrastructure.repositories.specification import Specification


class AIProviderEnabled(Specification[AIProvider]):
    """Matches enabled AI providers."""

    def to_expression(self, entity: type[AIProvider]):
        return entity.enabled == 1


class AIProviderByKind(Specification[AIProvider]):
    """Matches providers of a specific kind."""

    def __init__(self, kind: str) -> None:
        self._kind = kind

    def to_expression(self, entity: type[AIProvider]):
        return entity.provider_kind == self._kind


class AIModelEnabled(Specification[AIModel]):
    """Matches enabled models."""

    def to_expression(self, entity: type[AIModel]):
        return entity.enabled == 1


class AIModelByProvider(Specification[AIModel]):
    """Matches models exposed by a specific provider."""

    def __init__(self, provider_id: int) -> None:
        self._provider_id = provider_id

    def to_expression(self, entity: type[AIModel]):
        return entity.provider_id == self._provider_id


class AIInvocationByTask(Specification[AIInvocation]):
    """Matches invocations for a specific task."""

    def __init__(self, task_key: str) -> None:
        self._task_key = task_key

    def to_expression(self, entity: type[AIInvocation]):
        return entity.task_key == self._task_key


class AIInvocationFailed(Specification[AIInvocation]):
    """Matches failed invocations."""

    def to_expression(self, entity: type[AIInvocation]):
        return entity.status == "failed"