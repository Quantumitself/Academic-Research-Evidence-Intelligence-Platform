"""Tests for the collection service."""

from __future__ import annotations

import pytest

from academic_platform.application.collections.errors import (
    CollectionError,
    CollectionNotFoundError,
    CollectionValidationError,
)
from academic_platform.application.collections.model import CollectionKind
from academic_platform.application.collections.service import CollectionService
from academic_platform.infrastructure.database import Database
from academic_platform.infrastructure.database.base import Base
from academic_platform.infrastructure.database.models import (
    AuditEvent,
    Collection,
    CollectionItem,
    ResearchProject,
)
from academic_platform.infrastructure.repositories.factory import (
    _REPOSITORY_REGISTRY,
)
from academic_platform.infrastructure.repositories.manager import (
    RepositoryManager,
)


@pytest.fixture()
def database() -> Database:
    db = Database.in_memory()
    Base.metadata.create_all(db.engine)
    yield db
    db.dispose()


def _service(database: Database) -> CollectionService:
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        yield CollectionService(repositories)


def test_create_collection(database: Database) -> None:
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = CollectionService(repositories)
        view = service.create_collection(
            key="reading-list",
            title="Reading list",
            description="Papers to read",
        )
        assert view.key == "reading-list"
        assert view.kind is CollectionKind.MANUAL
        assert view.project_key is None


def test_create_collection_rejects_duplicate(database: Database) -> None:
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = CollectionService(repositories)
        service.create_collection(key="a")
    with pytest.raises(CollectionValidationError):
        with database.session() as session:
            repositories = RepositoryManager(session)
            repositories.register_all(dict(_REPOSITORY_REGISTRY))
            service = CollectionService(repositories)
            service.create_collection(key="a")


def test_create_collection_rejects_invalid_key(database: Database) -> None:
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = CollectionService(repositories)
        with pytest.raises(CollectionValidationError):
            service.create_collection(key="Invalid Key")


def test_create_project_collection_requires_project(database: Database) -> None:
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = CollectionService(repositories)
        with pytest.raises(CollectionValidationError):
            service.create_collection(
                key="pc", kind=CollectionKind.PROJECT
            )


def test_create_project_collection(database: Database) -> None:
    with database.session() as session:
        session.add(ResearchProject(key="proj-1", title="Study"))
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = CollectionService(repositories)
        view = service.create_collection(
            key="project-proj-1",
            title="Study — documents",
            kind=CollectionKind.PROJECT,
            project_key="proj-1",
        )
        assert view.is_project_linked
        assert view.project_key == "proj-1"


def test_create_smart_collection_requires_filter(database: Database) -> None:
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = CollectionService(repositories)
        with pytest.raises(CollectionValidationError):
            service.create_collection(
                key="smart-1", kind=CollectionKind.SMART
            )


def test_create_smart_collection_with_filter(database: Database) -> None:
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = CollectionService(repositories)
        view = service.create_collection(
            key="smart-1",
            kind=CollectionKind.SMART,
            filter_json='{"year_from": 2020}',
        )
        assert view.kind is CollectionKind.SMART


def test_update_collection(database: Database) -> None:
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = CollectionService(repositories)
        service.create_collection(key="a", title="Old")
        updated = service.update_collection("a", title="New")
        assert updated.title == "New"


def test_update_collection_unknown_raises(database: Database) -> None:
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = CollectionService(repositories)
        with pytest.raises(CollectionNotFoundError):
            service.update_collection("missing", title="X")


def test_delete_collection_removes_items(database: Database) -> None:
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = CollectionService(repositories)
        service.create_collection(key="a")
        service.add_item(
            "a", item_type="publication", item_identifier="pub-1"
        )
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = CollectionService(repositories)
        service.delete_collection("a")
    with database.session() as session:
        assert session.query(Collection).count() == 0
        assert session.query(CollectionItem).count() == 0


def test_add_item(database: Database) -> None:
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = CollectionService(repositories)
        service.create_collection(key="a")
        item = service.add_item(
            "a", item_type="publication", item_identifier="pub-1"
        )
        assert item.item_type == "publication"
        assert item.item_identifier == "pub-1"


def test_add_item_rejects_duplicate(database: Database) -> None:
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = CollectionService(repositories)
        service.create_collection(key="a")
        service.add_item(
            "a", item_type="publication", item_identifier="pub-1"
        )
    with pytest.raises(CollectionValidationError):
        with database.session() as session:
            repositories = RepositoryManager(session)
            repositories.register_all(dict(_REPOSITORY_REGISTRY))
            service = CollectionService(repositories)
            service.add_item(
                "a", item_type="publication", item_identifier="pub-1"
            )


def test_add_item_rejects_invalid_type(database: Database) -> None:
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = CollectionService(repositories)
        service.create_collection(key="a")
        with pytest.raises(CollectionValidationError):
            service.add_item(
                "a", item_type="bogus", item_identifier="x"
            )


def test_add_item_rejects_project_collection(database: Database) -> None:
    with database.session() as session:
        session.add(ResearchProject(key="proj-1", title="Study"))
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = CollectionService(repositories)
        service.create_collection(
            key="project-proj-1",
            kind=CollectionKind.PROJECT,
            project_key="proj-1",
        )
        with pytest.raises(CollectionValidationError):
            service.add_item(
                "project-proj-1",
                item_type="publication",
                item_identifier="pub-1",
            )


def test_list_items(database: Database) -> None:
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = CollectionService(repositories)
        service.create_collection(key="a")
        service.add_item(
            "a", item_type="publication", item_identifier="pub-1"
        )
        service.add_item(
            "a", item_type="publication", item_identifier="pub-2"
        )
        items = service.list_items("a")
        assert [i.item_identifier for i in items] == ["pub-1", "pub-2"]


def test_update_item_note(database: Database) -> None:
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = CollectionService(repositories)
        service.create_collection(key="a")
        item = service.add_item(
            "a", item_type="publication", item_identifier="pub-1"
        )
        updated = service.update_item(
            "a", item.identifier, note="Important reference."
        )
        assert updated.note == "Important reference."


def test_remove_item(database: Database) -> None:
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = CollectionService(repositories)
        service.create_collection(key="a")
        item = service.add_item(
            "a", item_type="publication", item_identifier="pub-1"
        )
        service.remove_item("a", item.identifier)
    with database.session() as session:
        assert session.query(CollectionItem).count() == 0


def test_remove_item_by_target(database: Database) -> None:
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = CollectionService(repositories)
        service.create_collection(key="a")
        service.add_item(
            "a", item_type="publication", item_identifier="pub-1"
        )
        assert service.remove_item_by_target(
            "a", item_type="publication", item_identifier="pub-1"
        ) is True
        assert service.remove_item_by_target(
            "a", item_type="publication", item_identifier="pub-1"
        ) is False


def test_reorder_items(database: Database) -> None:
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = CollectionService(repositories)
        service.create_collection(key="a")
        first = service.add_item(
            "a", item_type="publication", item_identifier="pub-1"
        )
        second = service.add_item(
            "a", item_type="publication", item_identifier="pub-2"
        )
        updated = service.reorder_items(
            "a", [second.identifier, first.identifier]
        )
        assert updated == 2
        items = service.list_items("a")
        assert [i.item_identifier for i in items] == ["pub-2", "pub-1"]


def test_find_item(database: Database) -> None:
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = CollectionService(repositories)
        service.create_collection(key="a")
        service.add_item(
            "a", item_type="publication", item_identifier="pub-1"
        )
        found = service.find_item("a", "publication", "pub-1")
        assert found is not None
        assert service.find_item("a", "publication", "pub-2") is None


def test_project_collection_key(database: Database) -> None:
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = CollectionService(repositories)
        assert service.project_collection_key("proj-1") == "project-proj-1"


def test_list_collections_for_project(database: Database) -> None:
    with database.session() as session:
        session.add(ResearchProject(key="proj-1", title="Study"))
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = CollectionService(repositories)
        service.create_collection(
            key="project-proj-1",
            kind=CollectionKind.PROJECT,
            project_key="proj-1",
        )
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        collections = CollectionService(repositories).list_collections_for_project(
            "proj-1"
        )
        assert [c.key for c in collections] == ["project-proj-1"]


def test_audit_events_recorded(database: Database) -> None:
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = CollectionService(repositories)
        service.create_collection(key="a", actor="alice")
        service.update_collection("a", title="New", actor="alice")
        item = service.add_item(
            "a",
            item_type="publication",
            item_identifier="pub-1",
            actor="alice",
        )
        service.remove_item("a", item.identifier, actor="alice")
    with database.session() as session:
        actions = {event.action for event in session.query(AuditEvent).all()}
        assert "collection.created" in actions
        assert "collection.updated" in actions
        assert "collection.item_added" in actions
        assert "collection.item_removed" in actions