"""Tests for the library application service."""

from __future__ import annotations

import pytest

from academic_platform.application.library.errors import (
    LibraryEntryNotFoundError,
)
from academic_platform.application.library.model import (
    LibraryFilter,
    LibrarySortDirection,
    LibrarySortField,
)
from academic_platform.application.library.service import LibraryService
from academic_platform.infrastructure.database import Database
from academic_platform.infrastructure.database.base import Base
from academic_platform.infrastructure.database.models import (
    DocumentAsset,
    DocumentChunk,
    DocumentMetadata,
)
from academic_platform.infrastructure.full_text_search.indexer import (
    FtsIndexer,
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


def _seed_document(
    database: Database,
    *,
    key: str,
    display_name: str,
    location: str = "/tmp/paper.pdf",
    processing_state: str = "extracted",
    size_bytes: int = 1024,
    title: str | None = None,
    authors: tuple[str, ...] = (),
    content: str = "",
) -> None:
    with database.session() as session:
        document = DocumentAsset(
            key=key,
            display_name=display_name,
            original_filename=display_name,
            location=location,
            checksum_sha256="0" * 64,
            size_bytes=size_bytes,
            processing_state=processing_state,
        )
        session.add(document)
        session.flush()
        if title or authors:
            session.add(
                DocumentMetadata(
                    document_id=document.id,
                    title=title or display_name,
                    authors_json="[" + ", ".join(f'"{a}"' for a in authors) + "]"
                    if authors
                    else None,
                )
            )
        if content:
            chunk = DocumentChunk(
                document_id=document.id,
                chunk_index=0,
                page_number=1,
                content=content,
            )
            session.add(chunk)
            session.flush()
            FtsIndexer(session).index_document(document, [chunk])


def test_list_returns_all_documents(database: Database) -> None:
    _seed_document(database, key="a", display_name="Alpha")
    _seed_document(database, key="b", display_name="Beta")
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = LibraryService(repositories)
        page = service.list_entries()
        assert page.total == 2
        assert {entry.key for entry in page.entries} == {"a", "b"}


def test_list_sorted_by_display_name(database: Database) -> None:
    _seed_document(database, key="a", display_name="Alpha")
    _seed_document(database, key="b", display_name="Beta")
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = LibraryService(repositories)
        page = service.list_entries(
            sort_field=LibrarySortField.DISPLAY_NAME,
            sort_direction=LibrarySortDirection.ASCENDING,
        )
        assert [entry.key for entry in page.entries] == ["a", "b"]


def test_filter_by_processing_state(database: Database) -> None:
    _seed_document(database, key="a", display_name="Alpha", processing_state="extracted")
    _seed_document(database, key="b", display_name="Beta", processing_state="pending")
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = LibraryService(repositories)
        page = service.list_entries(
            filter_state=LibraryFilter(processing_states=frozenset({"pending"}))
        )
        assert [entry.key for entry in page.entries] == ["b"]


def test_filter_by_extension(database: Database) -> None:
    _seed_document(database, key="a", display_name="Alpha", location="/tmp/a.pdf")
    _seed_document(database, key="b", display_name="Beta", location="/tmp/b.txt")
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = LibraryService(repositories)
        page = service.list_entries(
            filter_state=LibraryFilter(extensions=frozenset({".pdf"}))
        )
        assert [entry.key for entry in page.entries] == ["a"]


def test_search_matches_indexed_content(database: Database) -> None:
    _seed_document(
        database,
        key="a",
        display_name="Alpha",
        content="Content about measurement invariance.",
    )
    _seed_document(
        database,
        key="b",
        display_name="Beta",
        content="Content about regression.",
    )
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = LibraryService(repositories)
        page = service.list_entries(
            filter_state=LibraryFilter(search_text="invariance")
        )
        assert [entry.key for entry in page.entries] == ["a"]


def test_get_entry_returns_metadata(database: Database) -> None:
    _seed_document(
        database,
        key="a",
        display_name="Alpha",
        title="A Title",
        authors=("Author One", "Author Two"),
    )
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = LibraryService(repositories)
        entry = service.get_entry("a")
        assert entry.title == "A Title"
        assert entry.authors == ("Author One", "Author Two")


def test_get_entry_unknown_key_raises(database: Database) -> None:
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = LibraryService(repositories)
        with pytest.raises(LibraryEntryNotFoundError):
            service.get_entry("missing")


def test_delete_entry_removes_document_and_index(database: Database) -> None:
    _seed_document(
        database,
        key="a",
        display_name="Alpha",
        content="Indexed content about variance.",
    )
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = LibraryService(repositories)
        service.delete_entry("a")
    with database.session() as session:
        from academic_platform.infrastructure.full_text_search.query import (
            FtsQueryService,
        )

        assert session.query(DocumentAsset).count() == 0
        assert FtsQueryService(session).search_documents("variance") == []


def test_mark_missing_toggles_flag(database: Database) -> None:
    _seed_document(database, key="a", display_name="Alpha")
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        service = LibraryService(repositories)
        service.mark_missing("a")
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        entry = LibraryService(repositories).get_entry("a")
        assert entry.missing is True


def test_count_by_state(database: Database) -> None:
    _seed_document(database, key="a", display_name="A", processing_state="extracted")
    _seed_document(database, key="b", display_name="B", processing_state="extracted")
    _seed_document(database, key="c", display_name="C", processing_state="pending")
    with database.session() as session:
        repositories = RepositoryManager(session)
        repositories.register_all(dict(_REPOSITORY_REGISTRY))
        counts = LibraryService(repositories).count_by_state()
        assert counts["extracted"] == 2
        assert counts["pending"] == 1