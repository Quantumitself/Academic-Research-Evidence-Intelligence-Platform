"""Tests for the CollectionRepository and CollectionItemRepository."""

from __future__ import annotations

import pytest

from academic_platform.infrastructure.database import Database
from academic_platform.infrastructure.database.base import Base
from academic_platform.infrastructure.database.models import (
    Collection,
    ResearchProject,
)
from academic_platform.infrastructure.repositories.collection_repository import (
    CollectionItemRepository,
    CollectionRepository,
)
from academic_platform.infrastructure.repositories.errors import DuplicateEntityError


@pytest.fixture()
def database() -> Database:
    db = Database.in_memory()
    Base.metadata.create_all(db.engine)
    yield db
    db.dispose()


def test_find_by_key(database: Database) -> None:
    with database.session() as session:
        repo = CollectionRepository(session)
        repo.add(Collection(key="c1", title="A"))
    with database.session() as session:
        repo = CollectionRepository(session)
        found = repo.find_by_key("c1")
        assert found is not None
        assert found.title == "A"


def test_list_for_project(database: Database) -> None:
    with database.session() as session:
        project = ResearchProject(key="p1")
        session.add(project)
        session.flush()
        repo = CollectionRepository(session)
        repo.add(Collection(key="c1", kind="project", project_id=project.id, title="B"))
        repo.add(Collection(key="c2", kind="project", project_id=project.id, title="A"))
    with database.session() as session:
        repo = CollectionRepository(session)
        titles = [c.title for c in repo.list_for_project(1)]
        assert titles == ["A", "B"]


def test_item_count(database: Database) -> None:
    with database.session() as session:
        repo = CollectionRepository(session)
        collection = repo.add(Collection(key="c1"))
    with database.session() as session:
        item_repo = CollectionItemRepository(session)
        item_repo.add_item(collection.id, "publication", "p1")
        item_repo.add_item(collection.id, "publication", "p2")
    with database.session() as session:
        repo = CollectionRepository(session)
        assert repo.item_count(collection.id) == 2


def test_add_item_assigns_positions(database: Database) -> None:
    with database.session() as session:
        repo = CollectionRepository(session)
        collection = repo.add(Collection(key="c1"))
    with database.session() as session:
        item_repo = CollectionItemRepository(session)
        first = item_repo.add_item(collection.id, "publication", "p1")
        second = item_repo.add_item(collection.id, "publication", "p2")
        assert first.position == 1
        assert second.position == 2


def test_add_item_rejects_duplicate(database: Database) -> None:
    with database.session() as session:
        repo = CollectionRepository(session)
        collection = repo.add(Collection(key="c1"))
    with database.session() as session:
        item_repo = CollectionItemRepository(session)
        item_repo.add_item(collection.id, "publication", "p1")
    with pytest.raises(DuplicateEntityError):
        with database.session() as session:
            item_repo = CollectionItemRepository(session)
            item_repo.add_item(collection.id, "publication", "p1")


def test_remove_item(database: Database) -> None:
    with database.session() as session:
        repo = CollectionRepository(session)
        collection = repo.add(Collection(key="c1"))
    with database.session() as session:
        item_repo = CollectionItemRepository(session)
        item_repo.add_item(collection.id, "publication", "p1")
    with database.session() as session:
        item_repo = CollectionItemRepository(session)
        assert item_repo.remove_item(collection.id, "publication", "p1") is True
        assert item_repo.remove_item(collection.id, "publication", "p1") is False


def test_find_for_target(database: Database) -> None:
    with database.session() as session:
        repo = CollectionRepository(session)
        collection = repo.add(Collection(key="c1"))
    with database.session() as session:
        item_repo = CollectionItemRepository(session)
        item_repo.add_item(collection.id, "publication", "p1")
    with database.session() as session:
        item_repo = CollectionItemRepository(session)
        found = item_repo.find_for_target(collection.id, "publication", "p1")
        assert found is not None
        assert found.item_identifier == "p1"


def test_reorder(database: Database) -> None:
    with database.session() as session:
        repo = CollectionRepository(session)
        collection = repo.add(Collection(key="c1"))
    with database.session() as session:
        item_repo = CollectionItemRepository(session)
        item_repo.add_item(collection.id, "publication", "a")
        item_repo.add_item(collection.id, "publication", "b")
        item_repo.add_item(collection.id, "publication", "c")
    with database.session() as session:
        item_repo = CollectionItemRepository(session)
        updated = item_repo.reorder(collection.id, ["c", "b", "a"])
        assert updated == 3
    with database.session() as session:
        item_repo = CollectionItemRepository(session)
        ordered = [i.item_identifier for i in item_repo.list_for_collection(collection.id)]
        assert ordered == ["c", "b", "a"]


def test_list_for_collection_ordered(database: Database) -> None:
    with database.session() as session:
        repo = CollectionRepository(session)
        collection = repo.add(Collection(key="c1"))
    with database.session() as session:
        item_repo = CollectionItemRepository(session)
        item_repo.add_item(collection.id, "publication", "a")
        item_repo.add_item(collection.id, "publication", "b")
    with database.session() as session:
        item_repo = CollectionItemRepository(session)
        ordered = [i.item_identifier for i in item_repo.list_for_collection(collection.id)]
        assert ordered == ["a", "b"]