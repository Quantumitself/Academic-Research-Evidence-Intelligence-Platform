"""Tests for the FTS5 indexer."""

from __future__ import annotations

import pytest

from academic_platform.infrastructure.database import Database
from academic_platform.infrastructure.database.base import Base
from academic_platform.infrastructure.database.models import (
    Annotation,
    DocumentAsset,
    DocumentChunk,
    DocumentMetadata,
    Publication,
)
from academic_platform.infrastructure.database.models.fts import (
    FTS_DOCUMENTS_TABLE,
    FTS_NOTES_TABLE,
    FTS_PUBLICATIONS_TABLE,
)
from academic_platform.infrastructure.full_text_search.indexer import (
    FtsIndexer,
)
from sqlalchemy import text


@pytest.fixture()
def database() -> Database:
    db = Database.in_memory()
    Base.metadata.create_all(db.engine)
    yield db
    db.dispose()


def _seed_document(database: Database) -> int:
    with database.session() as session:
        document = DocumentAsset(
            key="doc-1",
            display_name="Paper",
            location="/tmp/paper.pdf",
            checksum_sha256="0" * 64,
        )
        session.add(document)
        session.flush()
        return document.id


def test_index_document_writes_rows(database: Database) -> None:
    document_id = _seed_document(database)
    with database.session() as session:
        document = session.get(DocumentAsset, document_id)
        chunks = [
            DocumentChunk(
                document_id=document_id,
                chunk_index=0,
                page_number=1,
                content="First page text with keyword alpha.",
            ),
            DocumentChunk(
                document_id=document_id,
                chunk_index=1,
                page_number=2,
                content="Second page text with keyword beta.",
            ),
        ]
        session.add_all(chunks)
        session.flush()
        metadata = DocumentMetadata(
            document_id=document_id, title="Paper Title", authors_json='["A"]'
        )
        session.add(metadata)
        session.flush()
        indexer = FtsIndexer(session)
        written = indexer.index_document(document, chunks, metadata)
        assert written == 2
        # Verify the FTS rows exist.
        rows = session.execute(
            text(f'SELECT document_key, content FROM "{FTS_DOCUMENTS_TABLE}"')
        ).all()
        assert len(rows) == 2
        keys = {row[0] for row in rows}
        assert keys == {"doc-1"}


def test_index_document_replaces_previous_rows(database: Database) -> None:
    document_id = _seed_document(database)
    with database.session() as session:
        document = session.get(DocumentAsset, document_id)
        first = [
            DocumentChunk(
                document_id=document_id,
                chunk_index=0,
                page_number=1,
                content="Old content.",
            )
        ]
        session.add_all(first)
        session.flush()
        indexer = FtsIndexer(session)
        indexer.index_document(document, first)
        # Replace with new chunks.
        session.query(DocumentChunk).delete()
        second = [
            DocumentChunk(
                document_id=document_id,
                chunk_index=0,
                page_number=1,
                content="New content.",
            )
        ]
        session.add_all(second)
        session.flush()
        indexer.index_document(document, second)
        rows = session.execute(
            text(f'SELECT content FROM "{FTS_DOCUMENTS_TABLE}"')
        ).all()
        contents = [row[0] for row in rows]
        assert contents == ["New content."]


def test_index_document_skips_empty_chunks(database: Database) -> None:
    document_id = _seed_document(database)
    with database.session() as session:
        document = session.get(DocumentAsset, document_id)
        chunks = [
            DocumentChunk(
                document_id=document_id,
                chunk_index=0,
                page_number=1,
                content="",
            ),
        ]
        session.add_all(chunks)
        session.flush()
        indexer = FtsIndexer(session)
        written = indexer.index_document(document, chunks)
        assert written == 0


def test_remove_document(database: Database) -> None:
    document_id = _seed_document(database)
    with database.session() as session:
        document = session.get(DocumentAsset, document_id)
        chunks = [
            DocumentChunk(
                document_id=document_id,
                chunk_index=0,
                page_number=1,
                content="Text.",
            )
        ]
        session.add_all(chunks)
        session.flush()
        indexer = FtsIndexer(session)
        indexer.index_document(document, chunks)
        removed = indexer.remove_document("doc-1")
        assert removed == 1
        rows = session.execute(
            text(f'SELECT content FROM "{FTS_DOCUMENTS_TABLE}"')
        ).all()
        assert rows == []


def test_index_publication(database: Database) -> None:
    with database.session() as session:
        publication = Publication(
            key="pub-1",
            title="A Study",
            abstract="An abstract about measurement.",
            venue="Journal",
            authors_json='["A. Author"]',
        )
        session.add(publication)
        session.flush()
        indexer = FtsIndexer(session)
        written = indexer.index_publication(publication)
        assert written == 1
        rows = session.execute(
            text(f'SELECT title, abstract FROM "{FTS_PUBLICATIONS_TABLE}"')
        ).all()
        assert rows[0][0] == "A Study"
        assert "measurement" in rows[0][1]


def test_remove_publication(database: Database) -> None:
    with database.session() as session:
        publication = Publication(key="pub-1", title="T")
        session.add(publication)
        session.flush()
        indexer = FtsIndexer(session)
        indexer.index_publication(publication)
        removed = indexer.remove_publication("pub-1")
        assert removed == 1


def test_index_annotation(database: Database) -> None:
    document_id = _seed_document(database)
    with database.session() as session:
        annotation = Annotation(
            document_id=document_id,
            kind="note",
            page_number=3,
            body="Important note about variance.",
        )
        session.add(annotation)
        session.flush()
        indexer = FtsIndexer(session)
        written = indexer.index_annotation(annotation, "doc-1")
        assert written == 1
        rows = session.execute(
            text(f'SELECT content FROM "{FTS_NOTES_TABLE}"')
        ).all()
        assert "variance" in rows[0][0]


def test_index_annotation_skips_empty(database: Database) -> None:
    document_id = _seed_document(database)
    with database.session() as session:
        annotation = Annotation(document_id=document_id, kind="note")
        session.add(annotation)
        session.flush()
        indexer = FtsIndexer(session)
        written = indexer.index_annotation(annotation, "doc-1")
        assert written == 0


def test_remove_annotation(database: Database) -> None:
    document_id = _seed_document(database)
    with database.session() as session:
        annotation = Annotation(
            document_id=document_id, kind="note", body="Note."
        )
        session.add(annotation)
        session.flush()
        indexer = FtsIndexer(session)
        indexer.index_annotation(annotation, "doc-1")
        removed = indexer.remove_annotation(annotation.id)
        assert removed == 1