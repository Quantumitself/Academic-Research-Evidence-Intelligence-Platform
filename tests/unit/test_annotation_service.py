"""Tests for the annotation service."""

from __future__ import annotations

import json

import pytest

from academic_platform.application.annotations.errors import (
    AnnotationError,
    AnnotationNotFoundError,
)
from academic_platform.application.annotations.model import (
    AnnotationColor,
    AnnotationKind,
)
from academic_platform.application.annotations.service import (
    AnnotationService,
)
from academic_platform.infrastructure.database import Database
from academic_platform.infrastructure.database.base import Base
from academic_platform.infrastructure.database.models import (
    Annotation,
    DocumentAsset,
)
from academic_platform.infrastructure.full_text_search.query import (
    FtsQueryService,
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


def test_create_note(database: Database) -> None:
    _seed_document(database)
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = AnnotationService(repositories)
        view = service.create_note("doc-1", 3, "A note about variance.")
        assert view.kind is AnnotationKind.NOTE
        assert view.body == "A note about variance."
        assert view.page_number == 3


def test_create_highlight(database: Database) -> None:
    _seed_document(database)
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = AnnotationService(repositories)
        view = service.create_highlight(
            "doc-1", 2, "Excerpt text", color=AnnotationColor.GREEN
        )
        assert view.kind is AnnotationKind.HIGHLIGHT
        assert view.color is AnnotationColor.GREEN
        assert view.text_excerpt == "Excerpt text"


def test_create_bookmark(database: Database) -> None:
    _seed_document(database)
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = AnnotationService(repositories)
        view = service.create_bookmark("doc-1", 5)
        assert view.kind is AnnotationKind.BOOKMARK
        assert view.page_number == 5


def test_create_rejects_invalid_page(database: Database) -> None:
    _seed_document(database)
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = AnnotationService(repositories)
        with pytest.raises(AnnotationError):
            service.create_note("doc-1", 0, "body")


def test_create_rejects_unknown_document(database: Database) -> None:
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = AnnotationService(repositories)
        with pytest.raises(AnnotationError):
            service.create_note("missing", 1, "body")


def test_list_for_document_orders_by_page(database: Database) -> None:
    _seed_document(database)
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = AnnotationService(repositories)
        service.create_note("doc-1", 3, "Page three")
        service.create_note("doc-1", 1, "Page one")
        service.create_note("doc-1", 2, "Page two")
        views = service.list_for_document("doc-1")
        assert [view.page_number for view in views] == [1, 2, 3]


def test_list_bookmarks(database: Database) -> None:
    _seed_document(database)
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = AnnotationService(repositories)
        service.create_note("doc-1", 1, "Note")
        service.create_bookmark("doc-1", 1)
        bookmarks = service.list_bookmarks("doc-1")
        assert len(bookmarks) == 1
        assert bookmarks[0].kind is AnnotationKind.BOOKMARK


def test_list_for_page(database: Database) -> None:
    _seed_document(database)
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = AnnotationService(repositories)
        service.create_note("doc-1", 1, "A")
        service.create_note("doc-1", 2, "B")
        assert len(service.list_for_page("doc-1", 1)) == 1


def test_update_note(database: Database) -> None:
    _seed_document(database)
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = AnnotationService(repositories)
        view = service.create_note("doc-1", 1, "Original")
        updated = service.update(view.identifier, body="Revised")
        assert updated.body == "Revised"


def test_update_unknown_raises(database: Database) -> None:
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = AnnotationService(repositories)
        with pytest.raises(AnnotationNotFoundError):
            service.update(999, body="x")


def test_delete_removes_annotation_and_index(database: Database) -> None:
    _seed_document(database)
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = AnnotationService(repositories)
        view = service.create_note("doc-1", 1, "Note about measurement.")
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = AnnotationService(repositories)
        service.delete(view.identifier)
    with database.session() as session:
        assert session.query(Annotation).count() == 0
        results = FtsQueryService(session).search_notes("measurement")
        assert results == []


def test_note_indexed_for_search(database: Database) -> None:
    _seed_document(database)
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = AnnotationService(repositories)
        service.create_note("doc-1", 1, "Content about invariance.")
    with database.session() as session:
        results = FtsQueryService(session).search_notes("invariance")
        assert results


def test_export_json(database: Database) -> None:
    _seed_document(database)
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = AnnotationService(repositories)
        service.create_note("doc-1", 1, "Note")
        service.create_bookmark("doc-1", 2)
        payload = service.export_to_json("doc-1")
    data = json.loads(payload)
    assert len(data) == 2
    kinds = {entry["kind"] for entry in data}
    assert kinds == {"note", "bookmark"}


def test_export_markdown(database: Database) -> None:
    _seed_document(database)
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = AnnotationService(repositories)
        service.create_note("doc-1", 1, "Note body")
        markdown = service.export_to_markdown("doc-1")
    assert "Note body" in markdown