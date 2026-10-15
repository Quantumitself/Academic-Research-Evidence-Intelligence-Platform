"""Tests for the AIModel and AITaskRouting models."""

from __future__ import annotations

import pytest

from academic_platform.infrastructure.database import DatabaseError

from academic_platform.infrastructure.database import Database
from academic_platform.infrastructure.database.base import Base
from academic_platform.infrastructure.database.models import (
    AIModel,
    AIProvider,
    AITaskRouting,
)


@pytest.fixture()
def database() -> Database:
    db = Database.in_memory()
    Base.metadata.create_all(db.engine)
    yield db
    db.dispose()


def _seed_provider(database: Database) -> int:
    with database.session() as session:
        provider = AIProvider(
            key="p",
            display_name="P",
            provider_kind="local_gguf",
        )
        session.add(provider)
        session.flush()
        return provider.id


def test_model_unique_per_provider(database: Database) -> None:
    provider_id = _seed_provider(database)
    with database.session() as session:
        session.add(AIModel(provider_id=provider_id, model_identifier="m1"))
    with pytest.raises(DatabaseError):
        with database.session() as session:
            session.add(AIModel(provider_id=provider_id, model_identifier="m1"))


def test_model_cascade_delete(database: Database) -> None:
    provider_id = _seed_provider(database)
    with database.session() as session:
        session.add(
            AIModel(provider_id=provider_id, model_identifier="m1")
        )
    with database.session() as session:
        provider = session.get(AIProvider, provider_id)
        assert provider is not None
        session.delete(provider)
    with database.session() as session:
        assert session.query(AIModel).count() == 0


def test_task_routing_unique_task(database: Database) -> None:
    with database.session() as session:
        session.add(AITaskRouting(task_key="article_summarization"))
    with pytest.raises(DatabaseError):
        with database.session() as session:
            session.add(AITaskRouting(task_key="article_summarization"))


def test_task_routing_provider_set_null_on_delete(database: Database) -> None:
    provider_id = _seed_provider(database)
    with database.session() as session:
        session.add(
            AITaskRouting(task_key="t", provider_id=provider_id)
        )
    with database.session() as session:
        provider = session.get(AIProvider, provider_id)
        assert provider is not None
        session.delete(provider)
    with database.session() as session:
        entry = session.query(AITaskRouting).one()
        assert entry.provider_id is None