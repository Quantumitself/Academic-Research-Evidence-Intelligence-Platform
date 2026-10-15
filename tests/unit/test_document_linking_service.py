"""Tests for the document linking service."""

from __future__ import annotations

import pytest

from academic_platform.application.document_linking.errors import (
    LinkingError,
    LinkingTargetNotFoundError,
)
from academic_platform.application.document_linking.model import LinkTarget
from academic_platform.application.document_linking.service import (
    DocumentLinkingService,
)
from academic_platform.infrastructure.database import Database
from academic_platform.infrastructure.database.base import Base
from academic_platform.infrastructure.database.models import (
    Collection,
    CollectionItem,
    DocumentAsset,
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


def _seed_document(database: Database, key: str = "doc-1") -> None:
    with database.session() as session:
        session.add(
            DocumentAsset(
                key=key,
                display_name="Paper",
                location="/tmp/paper.pdf",
                checksum_sha256="0" * 64,
            )
        )


def _seed_collection(database: Database, key: str = "col-1") -> None:
    with database.session() as session:
        session.add(
            Collection(key=key, title="Reading list", kind="manual")
        )


def _seed_project(database: Database, key: str = "proj-1") -> None:
    with database.session() as session:
        session.add(ResearchProject(key=key, title="Study"))


def test_list_collection_options(database: Database) -> None:
    _seed_collection(database, "col-1")
    _seed_collection(database, "col-2")
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = DocumentLinkingService(repositories)
        options = service.list_collection_options()
        assert {option.key for option in options} == {"col-1", "col-2"}


def test_list_project_options(database: Database) -> None:
    _seed_project(database, "proj-1")
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = DocumentLinkingService(repositories)
        options = service.list_project_options()
        assert [option.key for option in options] == ["proj-1"]


def test_link_to_collection(database: Database) -> None:
    _seed_document(database)
    _seed_collection(database)
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = DocumentLinkingService(repositories)
        result = service.link_document_to_collection("doc-1", "col-1")
        assert result.linked is True
        assert result.target is LinkTarget.COLLECTION
        assert result.affected == 1


def test_link_is_idempotent(database: Database) -> None:
    _seed_document(database)
    _seed_collection(database)
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = DocumentLinkingService(repositories)
        service.link_document_to_collection("doc-1", "col-1")
        second = service.link_document_to_collection("doc-1", "col-1")
        assert second.affected == 0


def test_unlink_from_collection(database: Database) -> None:
    _seed_document(database)
    _seed_collection(database)
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = DocumentLinkingService(repositories)
        service.link_document_to_collection("doc-1", "col-1")
        result = service.unlink_document_from_collection("doc-1", "col-1")
        assert result.linked is False
        assert result.affected == 1


def test_link_to_project_creates_collection(database: Database) -> None:
    _seed_document(database)
    _seed_project(database)
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = DocumentLinkingService(repositories)
        result = service.link_document_to_project("doc-1", "proj-1")
        assert result.linked is True
        assert result.target is LinkTarget.PROJECT
    with database.session() as session:
        collections = session.query(Collection).all()
        assert any(collection.kind == "project" for collection in collections)
        items = session.query(CollectionItem).all()
        assert any(item.item_type == "document" for item in items)


def test_link_to_project_reuses_collection(database: Database) -> None:
    _seed_document(database)
    _seed_project(database)
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = DocumentLinkingService(repositories)
        service.link_document_to_project("doc-1", "proj-1")
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = DocumentLinkingService(repositories)
        service.link_document_to_project("doc-1", "proj-1")
    with database.session() as session:
        collections = [
            c for c in session.query(Collection).all() if c.kind == "project"
        ]
        assert len(collections) == 1


def test_unlink_from_project(database: Database) -> None:
    _seed_document(database)
    _seed_project(database)
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = DocumentLinkingService(repositories)
        service.link_document_to_project("doc-1", "proj-1")
        result = service.unlink_document_from_project("doc-1", "proj-1")
        assert result.linked is False
        assert result.affected == 1


def test_links_for_document_lists_both(database: Database) -> None:
    _seed_document(database)
    _seed_collection(database)
    _seed_project(database)
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = DocumentLinkingService(repositories)
        service.link_document_to_collection("doc-1", "col-1")
        service.link_document_to_project("doc-1", "proj-1")
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        view = DocumentLinkingService(repositories).links_for_document("doc-1")
        assert [c.key for c in view.collections] == ["col-1"]
        assert [p.key for p in view.projects] == ["proj-1"]


def test_link_unknown_document_raises(database: Database) -> None:
    _seed_collection(database)
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = DocumentLinkingService(repositories)
        with pytest.raises(LinkingError):
            service.link_document_to_collection("missing", "col-1")


def test_link_unknown_collection_raises(database: Database) -> None:
    _seed_document(database)
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = DocumentLinkingService(repositories)
        with pytest.raises(LinkingTargetNotFoundError):
            service.link_document_to_collection("doc-1", "missing")