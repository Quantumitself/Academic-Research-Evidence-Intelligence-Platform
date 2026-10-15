"""Tests for the AI repositories."""

from __future__ import annotations

import datetime as dt

import pytest

from academic_platform.infrastructure.database import Database
from academic_platform.infrastructure.database.base import Base
from academic_platform.infrastructure.database.models import AIInvocation
from academic_platform.infrastructure.database.schemas import (
    AIModelCreate,
    AIProviderCreate,
    AITaskRoutingCreate,
)
from academic_platform.infrastructure.repositories.ai_provider_repository import (
    AIInvocationRepository,
    AIModelRepository,
    AIProviderRepository,
    AITaskRoutingRepository,
)
from academic_platform.infrastructure.repositories.errors import RepositoryError


@pytest.fixture()
def database() -> Database:
    db = Database.in_memory()
    Base.metadata.create_all(db.engine)
    yield db
    db.dispose()


def _create_provider(repo: AIProviderRepository, key: str = "local") -> int:
    provider = repo.create(
        AIProviderCreate(
            key=key,
            display_name=key.title(),
            provider_kind="local_gguf",
            endpoint_url="http://127.0.0.1:8080",
        )
    )
    return provider.id


def test_provider_find_and_list(database: Database) -> None:
    with database.session() as session:
        repo = AIProviderRepository(session)
        _create_provider(repo, key="b")
        _create_provider(repo, key="a")
    with database.session() as session:
        repo = AIProviderRepository(session)
        assert repo.find_by_key("a") is not None
        ordered = repo.list_all_ordered()
        assert [p.key for p in ordered] == ["a", "b"]


def test_provider_set_enabled(database: Database) -> None:
    with database.session() as session:
        repo = AIProviderRepository(session)
        provider_id = _create_provider(repo)
        provider = repo.set_enabled(provider_id, False)
        assert provider.enabled == 0
        assert provider.health_state == "disabled"


def test_provider_record_health(database: Database) -> None:
    with database.session() as session:
        repo = AIProviderRepository(session)
        provider_id = _create_provider(repo)
        provider = repo.record_health(
            provider_id,
            health_state="ok",
            tested_at="2024-01-01T00:00:00",
            error=None,
        )
        assert provider.health_state == "ok"


def test_provider_default_task_add_and_remove(database: Database) -> None:
    with database.session() as session:
        repo = AIProviderRepository(session)
        provider_id = _create_provider(repo)
        provider = repo.get_or_raise(provider_id)
        repo.add_default_task(provider, "article_summarization")
        repo.add_default_task(provider, "article_summarization")
        assert provider.default_for_tasks_json == '["article_summarization"]'
        repo.remove_default_task(provider, "article_summarization")
        assert provider.default_for_tasks_json == "[]"


def test_model_list_and_find(database: Database) -> None:
    with database.session() as session:
        provider_repo = AIProviderRepository(session)
        model_repo = AIModelRepository(session)
        provider_id = _create_provider(provider_repo)
        model_repo.create(AIModelCreate(provider_id=provider_id, model_identifier="m1"))
        model_repo.create(AIModelCreate(provider_id=provider_id, model_identifier="m2"))
    with database.session() as session:
        model_repo = AIModelRepository(session)
        models = model_repo.list_for_provider(provider_id)
        assert [m.model_identifier for m in models] == ["m1", "m2"]
        found = model_repo.find_by_identifier(provider_id, "m2")
        assert found is not None


def test_task_routing_set_primary_and_fallback(database: Database) -> None:
    with database.session() as session:
        provider_repo = AIProviderRepository(session)
        routing_repo = AITaskRoutingRepository(session)
        provider_id = _create_provider(provider_repo)
        routing_repo.set_primary("t", provider_id=provider_id, model_id=None)
        routing_repo.set_fallback("t", provider_id=None, model_id=None)
    with database.session() as session:
        routing_repo = AITaskRoutingRepository(session)
        entry = routing_repo.find_by_task("t")
        assert entry is not None
        assert entry.provider_id == provider_id


def test_task_routing_create_and_list(database: Database) -> None:
    with database.session() as session:
        repo = AITaskRoutingRepository(session)
        repo.create(AITaskRoutingCreate(task_key="b"))
        repo.create(AITaskRoutingCreate(task_key="a"))
    with database.session() as session:
        repo = AITaskRoutingRepository(session)
        keys = [r.task_key for r in repo.list_all_ordered()]
        assert keys == ["a", "b"]


def test_invocation_append_and_list(database: Database) -> None:
    with database.session() as session:
        repo = AIInvocationRepository(session)
        repo.append(
            AIInvocation(
                task_key="t",
                status="ok",
                started_at=dt.datetime(2024, 1, 1, 12, 0, 0),
            )
        )
        repo.append(
            AIInvocation(
                task_key="t",
                status="failed",
                started_at=dt.datetime(2024, 1, 1, 12, 1, 0),
            )
        )
    with database.session() as session:
        repo = AIInvocationRepository(session)
        recent = repo.list_recent()
        assert len(recent) == 2
        assert recent[0].status == "failed"
        assert len(repo.list_for_task("t")) == 2


def test_invocation_update_forbidden(database: Database) -> None:
    with database.session() as session:
        repo = AIInvocationRepository(session)
        invocation = repo.append(
            AIInvocation(
                task_key="t",
                status="ok",
                started_at=dt.datetime(2024, 1, 1),
            )
        )
        with pytest.raises(RepositoryError):
            repo.update(invocation, None)
        with pytest.raises(RepositoryError):
            repo.delete(invocation)
        with pytest.raises(RepositoryError):
            repo.update_fields(invocation.id, status="failed")
        with pytest.raises(RepositoryError):
            repo.delete_by_id(invocation.id)