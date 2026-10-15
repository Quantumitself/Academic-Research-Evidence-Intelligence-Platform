"""Tests for the DocumentAssetRepository and its sibling repositories."""

from __future__ import annotations

import pytest

from academic_platform.infrastructure.database import Database
from academic_platform.infrastructure.database.base import Base
from academic_platform.infrastructure.database.models import (
    Annotation,
    DocumentAsset,
    DocumentChunk,
)
from academic_platform.infrastructure.database.schemas import (
    DocumentAssetCreate,
    DocumentMetadataCreate,
)
from academic_platform.infrastructure.repositories.document_asset_repository import (
    AnnotationRepository,
    DocumentAssetRepository,
    DocumentChunkRepository,
    DocumentMetadataRepository,
)

_CHECKSUM = "0" * 64


@pytest.fixture()
def database() -> Database:
    db = Database.in_memory()
    Base.metadata.create_all(db.engine)
    yield db
    db.dispose()


def _seed_asset(database: Database, key: str = "doc-1", checksum: str = _CHECKSUM) -> int:
    with database.session() as session:
        repo = DocumentAssetRepository(session)
        asset = repo.create(
            DocumentAssetCreate(
                key=key,
                location="/tmp/a.pdf",
                checksum_sha256=checksum,
            )
        )
        return asset.id


def test_create_and_find_by_key(database: Database) -> None:
    _seed_asset(database)
    with database.session() as session:
        repo = DocumentAssetRepository(session)
        found = repo.find_by_key("doc-1")
        assert found is not None
        assert found.storage_mode == "managed_copy"


def test_find_by_checksum(database: Database) -> None:
    _seed_asset(database, key="doc-1", checksum=_CHECKSUM)
    _seed_asset(database, key="doc-2", checksum=_CHECKSUM)
    _seed_asset(database, key="doc-3", checksum="1" * 64)
    with database.session() as session:
        repo = DocumentAssetRepository(session)
        found = repo.find_by_checksum(_CHECKSUM)
        assert {asset.key for asset in found} == {"doc-1", "doc-2"}


def test_list_pending_processing(database: Database) -> None:
    _seed_asset(database, key="a")
    _seed_asset(database, key="b")
    with database.session() as session:
        repo = DocumentAssetRepository(session)
        pending = repo.list_pending_processing()
        assert {asset.key for asset in pending} == {"a", "b"}


def test_mark_missing_and_present(database: Database) -> None:
    identifier = _seed_asset(database)
    with database.session() as session:
        repo = DocumentAssetRepository(session)
        repo.mark_missing(identifier)
    with database.session() as session:
        repo = DocumentAssetRepository(session)
        assert repo.get_or_raise(identifier).missing == 1
        repo.mark_present(identifier)
    with database.session() as session:
        repo = DocumentAssetRepository(session)
        assert repo.get_or_raise(identifier).missing == 0


def test_metadata_upsert_creates_then_updates(database: Database) -> None:
    identifier = _seed_asset(database)
    with database.session() as session:
        repo = DocumentMetadataRepository(session)
        row = repo.upsert_for_document(identifier, title="Paper")
        assert row.title == "Paper"
    with database.session() as session:
        repo = DocumentMetadataRepository(session)
        row = repo.upsert_for_document(identifier, title="New")
        assert row.title == "New"
        assert repo.find_for_document(identifier) is not None


def test_metadata_upsert_replaces_fields(database: Database) -> None:
    identifier = _seed_asset(database)
    with database.session() as session:
        repo = DocumentMetadataRepository(session)
        repo.upsert_for_document(identifier, title="A", year=2020)
    with database.session() as session:
        repo = DocumentMetadataRepository(session)
        row = repo.upsert_for_document(identifier, title="B")
        assert row.title == "B"
        assert row.year is None


def test_chunk_replace_for_document(database: Database) -> None:
    identifier = _seed_asset(database)
    with database.session() as session:
        repo = DocumentChunkRepository(session)
        repo.replace_for_document(
            identifier,
            [
                DocumentChunk(
                    document_id=identifier,
                    chunk_index=0,
                    content="first",
                ),
                DocumentChunk(
                    document_id=identifier,
                    chunk_index=1,
                    content="second",
                ),
            ],
        )
    with database.session() as session:
        repo = DocumentChunkRepository(session)
        assert repo.count_for_document(identifier) == 2
        # Replace with a single chunk.
        repo.replace_for_document(
            identifier,
            [
                DocumentChunk(
                    document_id=identifier,
                    chunk_index=0,
                    content="only",
                ),
            ],
        )
    with database.session() as session:
        repo = DocumentChunkRepository(session)
        chunks = repo.list_for_document(identifier)
        assert [c.content for c in chunks] == ["only"]


def test_chunks_for_page(database: Database) -> None:
    identifier = _seed_asset(database)
    with database.session() as session:
        repo = DocumentChunkRepository(session)
        repo.replace_for_document(
            identifier,
            [
                DocumentChunk(
                    document_id=identifier,
                    chunk_index=0,
                    page_number=1,
                    content="a",
                ),
                DocumentChunk(
                    document_id=identifier,
                    chunk_index=1,
                    page_number=2,
                    content="b",
                ),
            ],
        )
    with database.session() as session:
        repo = DocumentChunkRepository(session)
        page_one = repo.chunks_for_page(identifier, 1)
        assert [c.content for c in page_one] == ["a"]


def test_annotation_lifecycle(database: Database) -> None:
    identifier = _seed_asset(database)
    with database.session() as session:
        repo = AnnotationRepository(session)
        repo.add(
            Annotation(
                document_id=identifier,
                kind="note",
                page_number=1,
                body="note",
            )
        )
        repo.add(
            Annotation(
                document_id=identifier,
                kind="bookmark",
                page_number=2,
            )
        )
    with database.session() as session:
        repo = AnnotationRepository(session)
        all_annotations = repo.list_for_document(identifier)
        assert len(all_annotations) == 2
        bookmarks = repo.list_bookmarks(identifier)
        assert len(bookmarks) == 1
        page_one = repo.list_for_page(identifier, 1)
        assert len(page_one) == 1


def test_annotation_require(database: Database) -> None:
    from academic_platform.infrastructure.repositories.errors import (
        EntityNotFoundError,
    )

    identifier = _seed_asset(database)
    with database.session() as session:
        repo = AnnotationRepository(session)
        with pytest.raises(EntityNotFoundError):
            repo.require(999)
        annotation = repo.add(
            Annotation(document_id=identifier, kind="note", body="x")
        )
    with database.session() as session:
        repo = AnnotationRepository(session)
        loaded = repo.require(annotation.id)
        assert loaded.body == "x"


def test_document_asset_repository_accepts_metadata_creation(database: Database) -> None:
    identifier = _seed_asset(database)
    with database.session() as session:
        repo = DocumentMetadataRepository(session)
        repo.create(
            DocumentMetadataCreate(document_id=identifier, title="A"),
        )
    with database.session() as session:
        repo = DocumentMetadataRepository(session)
        found = repo.find_for_document(identifier)
        assert found is not None
        assert found.title == "A"