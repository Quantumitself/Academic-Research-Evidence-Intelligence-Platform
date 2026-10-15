"""Repositories for AI providers, models, task routing, and invocations."""

from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from academic_platform.infrastructure.database.models import (
    AIInvocation,
    AIModel,
    AIProvider,
    AITaskRouting,
)
from academic_platform.infrastructure.repositories.base import Repository
from academic_platform.infrastructure.repositories.errors import RepositoryError


class AIProviderRepository(Repository[AIProvider]):
    """Repository for the ``ai_provider`` table."""

    entity = AIProvider

    def find_by_key(self, key: str) -> AIProvider | None:
        """Return the provider with the given key, or ``None``."""
        statement = select(AIProvider).where(AIProvider.key == key).limit(1)
        try:
            return self._session.execute(statement).scalars().first()
        except SQLAlchemyError as exc:
            raise RepositoryError(f"find_by_key failed: {exc}") from exc

    def list_enabled(self) -> list[AIProvider]:
        """Return every enabled provider ordered by display name."""
        statement = (
            select(AIProvider)
            .where(AIProvider.enabled == 1)
            .order_by(AIProvider.display_name)
        )
        try:
            return list(self._session.execute(statement).scalars().all())
        except SQLAlchemyError as exc:
            raise RepositoryError(f"list_enabled failed: {exc}") from exc

    def list_all_ordered(self) -> list[AIProvider]:
        """Return every provider ordered by display name."""
        statement = select(AIProvider).order_by(AIProvider.display_name)
        try:
            return list(self._session.execute(statement).scalars().all())
        except SQLAlchemyError as exc:
            raise RepositoryError(f"list_all_ordered failed: {exc}") from exc

    def set_enabled(self, provider_id: int, enabled: bool) -> AIProvider:
        """Enable or disable a provider and return the refreshed row."""
        provider = self.get_or_raise(provider_id)
        provider.enabled = 1 if enabled else 0
        provider.health_state = "unknown" if enabled else "disabled"
        try:
            self._session.flush()
        except SQLAlchemyError as exc:
            raise RepositoryError(f"set_enabled failed: {exc}") from exc
        return provider

    def record_health(
        self,
        provider_id: int,
        *,
        health_state: str,
        tested_at: str | None,
        error: str | None,
        runtime_info_json: str | None = None,
    ) -> AIProvider:
        """Record the outcome of a connection test."""
        provider = self.get_or_raise(provider_id)
        provider.health_state = health_state
        provider.last_tested_at = tested_at
        provider.last_error = error
        if runtime_info_json is not None:
            provider.runtime_info_json = runtime_info_json
        try:
            self._session.flush()
        except SQLAlchemyError as exc:
            raise RepositoryError(f"record_health failed: {exc}") from exc
        return provider

    def add_default_task(self, provider: AIProvider, task_key: str) -> AIProvider:
        """Add a task identifier to the provider's default-tasks list.

        Duplicate entries are ignored.
        """
        tasks = self._load_json_list(provider.default_for_tasks_json)
        if task_key in tasks:
            return provider
        tasks.append(task_key)
        provider.default_for_tasks_json = json.dumps(tasks)
        try:
            self._session.flush()
        except SQLAlchemyError as exc:
            raise RepositoryError(f"add_default_task failed: {exc}") from exc
        return provider

    def remove_default_task(self, provider: AIProvider, task_key: str) -> AIProvider:
        """Remove a task identifier from the provider's default-tasks list."""
        tasks = [t for t in self._load_json_list(provider.default_for_tasks_json) if t != task_key]
        provider.default_for_tasks_json = json.dumps(tasks)
        try:
            self._session.flush()
        except SQLAlchemyError as exc:
            raise RepositoryError(f"remove_default_task failed: {exc}") from exc
        return provider

    @staticmethod
    def _load_json_list(raw: str | None) -> list[str]:
        if not raw:
            return []
        try:
            data = json.loads(raw)
        except ValueError:
            return []
        if not isinstance(data, list):
            return []
        return [str(item) for item in data]


class AIModelRepository(Repository[AIModel]):
    """Repository for the ``ai_model`` table."""

    entity = AIModel

    def list_for_provider(self, provider_id: int) -> list[AIModel]:
        """Return the models of a provider ordered by identifier."""
        statement = (
            select(AIModel)
            .where(AIModel.provider_id == provider_id)
            .order_by(AIModel.model_identifier)
        )
        try:
            return list(self._session.execute(statement).scalars().all())
        except SQLAlchemyError as exc:
            raise RepositoryError(f"list_for_provider failed: {exc}") from exc

    def find_by_identifier(
        self, provider_id: int, model_identifier: str
    ) -> AIModel | None:
        """Return the model with the given identifier within a provider."""
        statement = (
            select(AIModel)
            .where(
                AIModel.provider_id == provider_id,
                AIModel.model_identifier == model_identifier,
            )
            .limit(1)
        )
        try:
            return self._session.execute(statement).scalars().first()
        except SQLAlchemyError as exc:
            raise RepositoryError(f"find_by_identifier failed: {exc}") from exc

    def set_enabled(self, model_id: int, enabled: bool) -> AIModel:
        """Enable or disable a model and return the refreshed row."""
        model = self.get_or_raise(model_id)
        model.enabled = 1 if enabled else 0
        model.health_state = "unknown" if enabled else "disabled"
        try:
            self._session.flush()
        except SQLAlchemyError as exc:
            raise RepositoryError(f"set_enabled failed: {exc}") from exc
        return model


class AITaskRoutingRepository(Repository[AITaskRouting]):
    """Repository for the ``ai_task_routing`` table."""

    entity = AITaskRouting

    def find_by_task(self, task_key: str) -> AITaskRouting | None:
        """Return the routing entry for a task, or ``None``."""
        statement = (
            select(AITaskRouting)
            .where(AITaskRouting.task_key == task_key)
            .limit(1)
        )
        try:
            return self._session.execute(statement).scalars().first()
        except SQLAlchemyError as exc:
            raise RepositoryError(f"find_by_task failed: {exc}") from exc

    def set_primary(
        self,
        task_key: str,
        *,
        provider_id: int | None,
        model_id: int | None,
    ) -> AITaskRouting:
        """Set the primary provider and model for a task.

        The routing entry is created when it does not exist.
        """
        entry = self.find_by_task(task_key)
        if entry is None:
            entry = AITaskRouting(task_key=task_key)
            self._session.add(entry)
        entry.provider_id = provider_id
        entry.model_id = model_id
        try:
            self._session.flush()
        except SQLAlchemyError as exc:
            raise RepositoryError(f"set_primary failed: {exc}") from exc
        return entry

    def set_fallback(
        self,
        task_key: str,
        *,
        provider_id: int | None,
        model_id: int | None,
    ) -> AITaskRouting:
        """Set the fallback provider and model for a task."""
        entry = self.find_by_task(task_key)
        if entry is None:
            entry = AITaskRouting(task_key=task_key)
            self._session.add(entry)
        entry.fallback_provider_id = provider_id
        entry.fallback_model_id = model_id
        try:
            self._session.flush()
        except SQLAlchemyError as exc:
            raise RepositoryError(f"set_fallback failed: {exc}") from exc
        return entry

    def list_all_ordered(self) -> list[AITaskRouting]:
        """Return every routing entry ordered by task key."""
        statement = select(AITaskRouting).order_by(AITaskRouting.task_key)
        try:
            return list(self._session.execute(statement).scalars().all())
        except SQLAlchemyError as exc:
            raise RepositoryError(f"list_all_ordered failed: {exc}") from exc


class AIInvocationRepository(Repository[AIInvocation]):
    """Repository for the ``ai_invocation`` table."""

    entity = AIInvocation

    def append(self, invocation: AIInvocation) -> AIInvocation:
        """Append an invocation record.

        The record is written once and never updated. The repository
        exposes this method rather than the base ``add`` to make the
        append-only intent explicit at the call site.
        """
        return self.add(invocation)

    def list_recent(self, *, limit: int = 50) -> list[AIInvocation]:
        """Return the most recent invocations, newest first."""
        statement = (
            select(AIInvocation)
            .order_by(AIInvocation.started_at.desc(), AIInvocation.id.desc())
            .limit(limit)
        )
        try:
            return list(self._session.execute(statement).scalars().all())
        except SQLAlchemyError as exc:
            raise RepositoryError(f"list_recent failed: {exc}") from exc

    def list_for_task(self, task_key: str, *, limit: int = 50) -> list[AIInvocation]:
        """Return invocations for a specific task, newest first."""
        statement = (
            select(AIInvocation)
            .where(AIInvocation.task_key == task_key)
            .order_by(AIInvocation.started_at.desc(), AIInvocation.id.desc())
            .limit(limit)
        )
        try:
            return list(self._session.execute(statement).scalars().all())
        except SQLAlchemyError as exc:
            raise RepositoryError(f"list_for_task failed: {exc}") from exc

    def update(self, entity: AIInvocation, payload) -> AIInvocation:  # type: ignore[override]
        raise RepositoryError("AI invocations are append-only and cannot be updated")

    def update_fields(self, identifier, **changes) -> AIInvocation:  # type: ignore[override]
        raise RepositoryError("AI invocations are append-only and cannot be updated")

    def delete(self, entity: AIInvocation) -> None:  # type: ignore[override]
        raise RepositoryError("AI invocations are append-only and cannot be deleted")

    def delete_by_id(self, identifier) -> bool:  # type: ignore[override]
        raise RepositoryError("AI invocations are append-only and cannot be deleted")