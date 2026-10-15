"""Tests for the FTS5 index rebuilder."""

from __future__ import annotations

import pytest

from academic_platform.infrastructure.database import Database
from academic_platform.infrastructure.database.base import Base
from academic_platform.infrastructure.database.models import (
    Annotation,
    DocumentAsset,
    DocumentChunk,
    Publication,
)
from academic_platform.infrastructure.full_text_search.query import (
    FtsQueryService,
)
from academic_platform.infrastructure.full_text_search.rebuilder import (
    FtsRebuilder,
    FtsRebuildReport,
)
from sqlalchemy import text


@pytest.fixture()
def database() -> Database:
    db = Database.in_memory()
    Base.metadata.create_all(db.engine)
    yield db
    db.dispose()


def _seed_primary(database: Database) -> None:
    with database.session() as session:
        document = DocumentAsset(
            key="doc-1",
            display_name="Paper",
            location="/tmp/paper.pdf",
            checksum_sha256="0" * 64,
        )
        session.add(document)
        session.flush()
        session.add(
            DocumentChunk(
                document_id=document.id,
                chunk_index=0,
                page_number=1,
                content="Content with keyword delta.",
            )
        )
        session.add(
            Annotation(
                document_id=document.id,
                kind="note",
                page_number=1,
                body="A note about delta.",
            )
        )
        session.add(
            Publication(
                key="pub-1",
                title="Publication with keyword delta",
                abstract="Abstract mentioning delta.",
            )
        )


def test_rebuild_populates_index(database: Database) -> None:
    _seed_primary(database)
    with database.session() as session:
        report = FtsRebuilder(session).rebuild()
        assert isinstance(report, FtsRebuildReport)
        assert report.documents_indexed == 1
        assert report.document_chunks_indexed == 1
        assert report.publications_indexed == 1
        assert report.annotations_indexed == 1


def test_rebuild_is_idempotent(database: Database) -> None:
    _seed_primary(database)
    with database.session() as session:
        FtsRebuilder(session).rebuild()
    with database.session() as session:
        report = FtsRebuilder(session).rebuild()
        assert report.documents_indexed == 1
    # Query the index; there should be exactly one hit per domain.
    with database.session() as session:
        service = FtsQueryService(session)
        assert len(service.search_documents("delta")) == 1
        assert len(service.search_publications("delta")) == 1
        assert len(service.search_notes("delta")) == 1


def test_rebuild_from_empty(database: Database) -> None:
    with database.session() as session:
        report = FtsRebuilder(session).rebuild()
        assert report.documents_indexed == 0
        assert report.publications_indexed == 0
        assert report.annotations_indexed == 0


def test_rebuild_clears_stale_rows(database: Database) -> None:
    _seed_primary(database)
    with database.session() as session:
        # Insert a stale FTS row that is not backed by a primary row.
        from academic_platform.infrastructure.database.models.fts import (
            FTS_DOCUMENTS_TABLE,
        )

        session.execute(
            text(
                f'INSERT INTO "{FTS_DOCUMENTS_TABLE}" '
                "(document_key, chunk_index, page_number, title, authors, content) "
                "VALUES ('stale', 0, 0, '', '', 'stale content');"
            )
        )
    with database.session() as session:
        FtsRebuilder(session).rebuild()
    with database.session() as session:
        service = FtsQueryService(session)
        assert not service.search_documents("stale")