"""Tests for the Collection and CollectionItem models."""

from __future__ import annotations

import pytest

from academic_platform.infrastructure.database import DatabaseError

from academic_platform.infrastructure.database import Database
from academic_platform.infrastructure.database.base import Base
from academic_platform.infrastructure.database.models import (
    Collection,
    CollectionItem,
    ResearchProject,
)


@pytest.fixture()
def database() -> Database:
    db = Database.in_memory()
    Base.metadata.create_all(db.engine)
    yield db
    db.dispose()


def test_manual_collection(database: Database) -> None:
    with database.session() as session:
        collection = Collection(key="c1", title="Reading list")
        session.add(collection)
        session.flush()
        assert collection.kind == "manual"
        assert collection.project_id is None


def test_project_linked_collection(database: Database) -> None:
    with database.session() as session:
        project = ResearchProject(key="p1")
        session.add(project)
        session.flush()
        collection = Collection(key="c1", kind="project", project_id=project.id)
        session.add(collection)
        session.flush()
        assert collection.project_id == project.id


def test_project_linked_collection_requires_project(database: Database) -> None:
    with pytest.raises(DatabaseError):
        with database.session() as session:
            session.add(Collection(key="c1", kind="project", project_id=None))


def test_non_project_collection_rejects_project(database: Database) -> None:
    with pytest.raises(DatabaseError):
        with database.session() as session:
            project = ResearchProject(key="p1")
            session.add(project)
            session.flush()
            session.add(
                Collection(key="c1", kind="manual", project_id=project.id)
            )


def test_collection_item_unique_target(database: Database) -> None:
    with database.session() as session:
        collection = Collection(key="c1")
        session.add(collection)
        session.flush()
        session.add(
            CollectionItem(
                collection_id=collection.id,
                item_type="publication",
                item_identifier="pub-1",
            )
        )
    with pytest.raises(DatabaseError):
        with database.session() as session:
            session.add(
                CollectionItem(
                    collection_id=1,
                    item_type="publication",
                    item_identifier="pub-1",
                )
            )


def test_collection_item_invalid_type_rejected(database: Database) -> None:
    with pytest.raises(DatabaseError):
        with database.session() as session:
            collection = Collection(key="c1")
            session.add(collection)
            session.flush()
            session.add(
                CollectionItem(
                    collection_id=collection.id,
                    item_type="bogus",
                    item_identifier="x",
                )
            )


def test_cascade_delete_removes_items(database: Database) -> None:
    with database.session() as session:
        collection = Collection(key="c1")
        session.add(collection)
        session.flush()
        session.add(
            CollectionItem(
                collection_id=collection.id,
                item_type="publication",
                item_identifier="pub-1",
            )
        )
    with database.session() as session:
        collection = session.get(Collection, 1)
        assert collection is not None
        session.delete(collection)
    with database.session() as session:
        assert session.query(CollectionItem).count() == 0