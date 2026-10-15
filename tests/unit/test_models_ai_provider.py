"""Tests for the AIProvider model."""

from __future__ import annotations

import pytest

from academic_platform.infrastructure.database import DatabaseError

from academic_platform.infrastructure.database import Database
from academic_platform.infrastructure.database.base import Base
from academic_platform.infrastructure.database.models import AIProvider


@pytest.fixture()
def database() -> Database:
    db = Database.in_memory()
    Base.metadata.create_all(db.engine)
    yield db
    db.dispose()


def _valid_provider(**overrides) -> AIProvider:
    defaults = {
        "key": "local-llama",
        "display_name": "Local Llama",
        "provider_kind": "local_gguf",
        "endpoint_url": "http://127.0.0.1:8080",
    }
    defaults.update(overrides)
    return AIProvider(**defaults)


def test_create_and_read(database: Database) -> None:
    with database.session() as session:
        provider = _valid_provider()
        session.add(provider)
        session.flush()
        identifier = provider.id
    with database.session() as session:
        loaded = session.get(AIProvider, identifier)
        assert loaded is not None
        assert loaded.enabled == 1
        assert loaded.health_state == "unknown"
        assert loaded.default_for_tasks_json == "[]"


def test_key_unique(database: Database) -> None:
    with database.session() as session:
        session.add(_valid_provider())
    with pytest.raises(DatabaseError):
        with database.session() as session:
            session.add(_valid_provider(display_name="Other"))


def test_invalid_kind_rejected(database: Database) -> None:
    with pytest.raises(DatabaseError):
        with database.session() as session:
            session.add(_valid_provider(provider_kind="bogus"))


def test_invalid_auth_rejected(database: Database) -> None:
    with pytest.raises(DatabaseError):
        with database.session() as session:
            session.add(_valid_provider(auth_type="bogus"))


def test_invalid_health_rejected(database: Database) -> None:
    with pytest.raises(DatabaseError):
        with database.session() as session:
            session.add(_valid_provider(health_state="bogus"))